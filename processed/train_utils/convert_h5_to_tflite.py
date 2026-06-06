import tempfile
import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional

import tensorflow as tf
from tensorflow.keras import layers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def compute_masked_pooling(inputs):
    x_val, lens_val = inputs
    # Use static shape if available to avoid TFLite MLIR compilation errors
    t = x_val.shape[1]
    if t is None:
        t = tf.shape(x_val)[1]
    
    mask = tf.sequence_mask(lens_val, maxlen=t, dtype=x_val.dtype)
    mask = tf.expand_dims(mask, axis=-1)
    x_masked = x_val * mask
    
    # Cast lens_val to float32 before max to avoid type inference issues
    lens_float = tf.cast(lens_val, x_val.dtype)
    denom = tf.maximum(lens_float, 1.0)
    denom = tf.expand_dims(denom, axis=-1)
    
    return tf.reduce_sum(x_masked, axis=1) / denom


def build_tcn_model(
    in_dim: int,
    num_classes: int,
    window_size: Optional[int] = None,
    channels: int = 64,
    levels: int = 3,
    kernel_size: int = 5,
    dropout: float = 0.3,
    use_proj: bool = True,
    proj_dim: Optional[int] = None,
) -> tf.keras.Model:
    """Builds the TCN model with fixed or dynamic time dimension."""
    # Using window_size if provided for better TFLite optimization, else None (dynamic)
    inputs = tf.keras.Input(shape=(window_size, in_dim), name="inputs", dtype=tf.float32)
    lengths = tf.keras.Input(shape=(), dtype=tf.int32, name="lengths")

    proj_dim = proj_dim or channels
    
    x = inputs
    if use_proj and in_dim != proj_dim:
        x = layers.Conv1D(filters=proj_dim, kernel_size=1, padding='same', name="proj")(x)
        
    current_in = proj_dim if (use_proj and in_dim != proj_dim) else in_dim
    
    for i in range(levels):
        dilation = 2 ** i
        # Conv1
        c1 = layers.Conv1D(
            filters=channels,
            kernel_size=kernel_size,
            padding='causal',
            dilation_rate=dilation,
            kernel_initializer='he_normal',
            name=f"tblock_{i}_conv1"
        )(x)
        r1 = layers.ReLU(name=f"tblock_{i}_relu1")(c1)
        d1 = layers.Dropout(dropout, name=f"tblock_{i}_drop1")(r1)
        
        # Conv2
        c2 = layers.Conv1D(
            filters=channels,
            kernel_size=kernel_size,
            padding='causal',
            dilation_rate=dilation,
            kernel_initializer='he_normal',
            name=f"tblock_{i}_conv2"
        )(d1)
        r2 = layers.ReLU(name=f"tblock_{i}_relu2")(c2)
        d2 = layers.Dropout(dropout, name=f"tblock_{i}_drop2")(r2)
        
        # Downsample
        if current_in != channels:
            res = layers.Conv1D(
                filters=channels,
                kernel_size=1,
                padding='same',
                kernel_initializer='he_normal',
                name=f"tblock_{i}_downsample"
            )(x)
        else:
            res = x
            
        x = layers.Add(name=f"tblock_{i}_add")([d2, res])
        x = layers.ReLU(name=f"tblock_{i}_out_relu")(x)
        current_in = channels
        
    # Masked Global Average Pooling
    pooled = layers.Lambda(compute_masked_pooling, name="masked_pool")([x, lengths])
    
    # Force float32 for mixed precision stability
    logits = layers.Dense(num_classes, name="classifier", dtype=tf.float32)(pooled)
    
    model = tf.keras.Model(inputs=[inputs, lengths], outputs=logits, name="tcn_classifier")
    return model


def convert_model(h5_path: Path, window_size: Optional[int] = 60, optimize: bool = True):
    """Converts a specific .h5 model to .tflite."""
    if not h5_path.exists():
        logger.error(f"File not found: {h5_path}")
        return

    json_path = h5_path.with_suffix('.json')
    if not json_path.exists():
        logger.error(f"Missing config JSON for {h5_path}. Cannot infer model architecture.")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {json_path}: {e}")
        return

    config = meta.get("config", {})
    in_dim = meta.get("in_dim") or config.get("in_dim") or 126
    num_classes = meta.get("num_classes") or config.get("num_classes")
    
    if not num_classes:
        logger.error(f"Could not determine num_classes from {json_path}")
        return

    channels = config.get("channels", 64)
    levels = config.get("levels", 3)
    kernel_size = config.get("kernel_size", 5)

    logger.info(f"Building model architecture (in_dim={in_dim}, num_classes={num_classes}, window_size={window_size})...")
    model = build_tcn_model(
        in_dim=in_dim,
        num_classes=num_classes,
        window_size=window_size,
        channels=channels,
        levels=levels,
        kernel_size=kernel_size,
        dropout=0.0  # Dropout not needed for inference
    )

    logger.info(f"Loading weights from {h5_path}...")
    try:
        model.load_weights(h5_path)
    except Exception as e:
        logger.error(f"Failed to load weights: {e}")
        return

    # Convert to TFLite using SavedModel (avoids Keras 3 MLIR frontend bugs)
    logger.info("Exporting to temporary SavedModel for conversion...")
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            model.export(tmpdir)
        except Exception as e:
            logger.error(f"Failed to export model to SavedModel: {e}")
            return
            
        logger.info("Initializing TFLite Converter from SavedModel...")
        converter = tf.lite.TFLiteConverter.from_saved_model(tmpdir)
        
        # Optional: Enable optimization for smaller footprint and faster inference
        if optimize:
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
        
        # Required for some complex ops like sequence_mask, depending on TF version
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS,
            tf.lite.OpsSet.SELECT_TF_OPS
        ]

        logger.info("Converting model (this may take a moment)...")
        try:
            tflite_model = converter.convert()
        except Exception as e:
            logger.error(f"TFLite conversion failed: {e}")
            return

    out_path = h5_path.with_suffix('.tflite')
    with open(out_path, 'wb') as f:
        f.write(tflite_model)
    
    logger.info(f"Successfully saved TFLite model to: {out_path} ({len(tflite_model) / 1024:.2f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Convert TCN .h5 models to .tflite format.")
    parser.add_argument("--input", type=str, default="outputs",
                        help="Path to a specific .h5 file or directory containing .h5 files.")
    parser.add_argument("--window", type=int, default=60,
                        help="Fixed window size for the TFLite model. Set to 0 for dynamic shape (may be slower/unstable).")
    parser.add_argument("--no-opt", action="store_true",
                        help="Disable TFLite DEFAULT optimization (quantization).")
    args = parser.parse_args()

    input_path = Path(args.input)
    window_size = args.window if args.window > 0 else None
    optimize = not args.no_opt

    if input_path.is_file():
        if input_path.suffix == '.h5':
            convert_model(input_path, window_size, optimize)
        else:
            logger.error("Input must be a .h5 file or a directory.")
    elif input_path.is_dir():
        h5_files = list(input_path.glob("*.h5"))
        if not h5_files:
            logger.info(f"No .h5 files found in {input_path}")
            return
        
        logger.info(f"Found {len(h5_files)} .h5 files. Starting conversion...")
        for h5_file in h5_files:
            logger.info(f"--- Processing {h5_file.name} ---")
            convert_model(h5_file, window_size, optimize)
    else:
        logger.error(f"Path does not exist: {input_path}")


if __name__ == "__main__":
    main()
