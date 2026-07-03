import os

def create_test_structure(base_path="tests"):
    structure = {
        "functional_testing": {
            "unit_testing": {
                "backend": ["core", "schemas", "services"],
                "frontend": ["shared", "features/auth"]
            },
            "component_testing": {
                "backend": ["fixtures"],
                "frontend": ["shared", "features"]
            },
            "integration_testing": {
                "backend_api": [],
                "frontend_hooks": []
            },
            "system_testing": {
                "config": [],
                "helpers": [],
                "specs": []
            },
            "smoke_testing": [],
            "sanity_testing": [],
            "regression_testing": [],
            "user_acceptance_testing": []
        },
        "non_functional_testing": {
            "performance_testing": {
                "load_testing": [],
                "stress_testing": []
            },
            "security_testing": {
                "payloads": []
            },
            "scalability_testing": [],
            "reliability_testing": [],
            "usability_testing": [],
            "interoperability_testing": []
        }
    }

    def build_tree(current_path, tree):
        if isinstance(tree, dict):
            for k, v in tree.items():
                p = os.path.join(current_path, k)
                os.makedirs(p, exist_ok=True)
                build_tree(p, v)
        elif isinstance(tree, list):
            for item in tree:
                p = os.path.join(current_path, item)
                os.makedirs(p, exist_ok=True)
                # create a .gitkeep so git tracks it
                with open(os.path.join(p, ".gitkeep"), "w") as f:
                    pass

    build_tree(base_path, structure)

    # Add .gitkeep to leaf directories that might be empty
    for root, dirs, files in os.walk(base_path):
        if not dirs and not files:
            with open(os.path.join(root, ".gitkeep"), "w") as f:
                pass

if __name__ == "__main__":
    create_test_structure()
    print("Scaffolded test structure successfully!")
