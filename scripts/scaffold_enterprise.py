import os
from pathlib import Path

def create_structure(base_dir: str, structure: dict):
    for key, value in structure.items():
        if key == "__files__":
            for file_name in value:
                file_path = os.path.join(base_dir, file_name)
                if not os.path.exists(file_path):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        if file_name.endswith('.md'):
                            f.write(f"# {file_name}\\n")
            continue
            
        if isinstance(value, dict):
            # It's a directory
            dir_path = os.path.join(base_dir, key)
            os.makedirs(dir_path, exist_ok=True)
            create_structure(dir_path, value)
        elif isinstance(value, list):
            # It's a directory containing files
            dir_path = os.path.join(base_dir, key)
            os.makedirs(dir_path, exist_ok=True)
            for file_name in value:
                file_path = os.path.join(dir_path, file_name)
                # Create empty file if not exists
                if not os.path.exists(file_path):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        if file_name.endswith('__init__.py'):
                            pass # empty init
                        elif file_name.endswith('.md'):
                            f.write(f"# {file_name}\\n")
                        else:
                            pass # empty file

# Define the structure based on the approved implementation plan
project_structure = {
    "signbridge-prod": {
        "system": {
            "legal": [".gitkeep"],
            "assets": {
                "images": [".gitkeep"],
                "documents": [".gitkeep"]
            },
            "configs": [".gitkeep"]
        },
        "workspace_template": {
            "raw": [".gitkeep"],
            "samples": [".gitkeep"],
            "thumbnails": [".gitkeep"],
            "features": [".gitkeep"],
            "datasets": [".gitkeep"],
            "models": [".gitkeep"],
            "training-logs": [".gitkeep"],
            "documents": [".gitkeep"]
        }
    },
    "backend": {
        "app": {
            "core": ["__init__.py", "config.py", "security.py", "dependencies.py", "exceptions.py", "logging.py", "constants.py", "rbac_model.conf", "casbin_enforcer.py"],
            "middleware": ["__init__.py", "request_id.py", "cors.py", "auth_guard.py", "tenant_context.py", "authorization_guard.py", "audit_logger.py", "rate_limiter.py"],
            "schemas": ["__init__.py", "common.py", "auth.py", "user.py", "workspace.py", "class_.py", "sample.py", "session.py", "training.py", "dataset.py", "model.py", "legal.py"],
            "repositories": ["__init__.py", "base.py", "user_repo.py", "workspace_repo.py", "class_repo.py", "sample_repo.py", "session_repo.py", "dataset_repo.py", "training_repo.py", "model_repo.py", "audit_repo.py", "legal_repo.py", "minio_repo.py", "redis_repo.py"],
            "services": ["__init__.py", "auth_service.py", "upload_service.py", "class_service.py", "sample_service.py", "training_service.py", "trash_service.py", "export_service.py", "workspace_service.py", "quota_service.py", "dataset_service.py", "model_service.py", "realtime_service.py", "legal_service.py", "notification_service.py"],
            "routers": {
                "__files__": ["__init__.py", "registry.py"],
                "v1": ["__init__.py", "auth.py", "users.py", "workspaces.py", "classes.py", "samples.py", "sessions.py", "upload.py", "training.py", "datasets.py", "models.py", "trash.py", "realtime.py", "legal.py", "admin.py", "health.py"]
            },
            "workers": ["__init__.py", "celery_app.py", "training_tasks.py", "sync_tasks.py", "resource_tasks.py", "cleanup_tasks.py"],
            "processing": ["__init__.py", "utils.py"],
            "db": ["__init__.py", "session.py", "base.py"],
            "__files__": ["main.py"]
        },
        "migrations": {
            "versions": [".gitkeep"],
            "__files__": ["env.py", "alembic.ini"]
        },
        "static": {
            "temp_images": [".gitkeep"],
            "temp_docs": [".gitkeep"]
        }
    },
    "frontend": {
        "src": {
            "app": ["index.ts"],
            "assets": {
                "images": [".gitkeep"],
                "icons": [".gitkeep"],
                "documents": [".gitkeep"],
                "fonts": [".gitkeep"]
            },
            "shared": ["index.ts"],
            "entities": ["index.ts"],
            "features": ["index.ts"],
            "widgets": ["index.ts"],
            "pages": ["index.ts"],
            "types": ["index.ts"]
        }
    },
    "tests": {
        "functional_testing": {
            "unit_testing": ["README.md", "__init__.py"],
            "component_testing": ["README.md", "__init__.py"],
            "integration_testing": ["README.md", "__init__.py"],
            "system_testing": ["README.md", "__init__.py"],
            "smoke_testing": ["README.md", "__init__.py"],
            "sanity_testing": ["README.md", "__init__.py"],
            "regression_testing": ["README.md", "__init__.py"],
            "user_acceptance_testing": ["README.md", "__init__.py"]
        },
        "non_functional_testing": {
            "performance_testing": ["README.md", "__init__.py"],
            "security_testing": ["README.md", "__init__.py"],
            "scalability_testing": ["README.md", "__init__.py"],
            "reliability_testing": ["README.md", "__init__.py"],
            "usability_testing": ["README.md", "__init__.py"],
            "interoperability_testing": ["README.md", "__init__.py"]
        }
    }
}

if __name__ == "__main__":
    base_dir = "e:\\CTU_ProjectOutside\\VOYA-Collector"
    create_structure(base_dir, project_structure)
    print("Scaffolding complete!")
