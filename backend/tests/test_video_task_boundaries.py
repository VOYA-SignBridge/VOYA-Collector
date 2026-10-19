"""Behavior checks for the dataset video-processing task boundary."""

from app.modules.dataset import video_tasks


def test_video_task_forwards_metadata_to_pipeline(monkeypatch) -> None:
    received = {}

    def process_video_job(**kwargs):
        received.update(kwargs)
        return {"saved": ["sample.npz"]}

    monkeypatch.setattr(video_tasks, "process_video_job", process_video_job)

    result = video_tasks.enqueue_process_video.run(
        video_path="/dataset/raw/video.mp4",
        user="collector",
        label="hello",
        session_id="session-1",
        dialect="hoa-de",
        language="vn",
        user_id="user-1",
    )

    assert result == {"status": "done", "result": {"saved": ["sample.npz"]}}
    assert received == {
        "video_path": "/dataset/raw/video.mp4",
        "user": "collector",
        "user_id": "user-1",
        "label": "hello",
        "session_id": "session-1",
        "dialect": "hoa-de",
        "language": "vn",
    }


def test_video_task_removes_downloaded_temporary_file(tmp_path, monkeypatch) -> None:
    temporary_video = tmp_path / "download.mp4"
    temporary_video.write_bytes(b"video")

    monkeypatch.setattr(
        video_tasks,
        "_download_from_storage",
        lambda _url: str(temporary_video),
    )
    monkeypatch.setattr(
        video_tasks,
        "process_video_job",
        lambda **_kwargs: {"saved": []},
    )

    video_tasks.enqueue_process_video.run(
        video_path="gdrive://file-id",
        user="collector",
        label="hello",
        session_id="session-1",
    )

    assert not temporary_video.exists()
