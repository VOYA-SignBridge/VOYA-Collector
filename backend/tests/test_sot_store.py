"""LocalSotStore behavior (the filesystem-backed SotStore used in tests)."""

from __future__ import annotations

import pytest

from app.sot.store import LocalSotStore, SotReadOnlyError, read_text, write_text


def test_write_read_exists(tmp_path):
    store = LocalSotStore(tmp_path / "SOT")
    assert store.exists("a/b.txt") is False
    store.write_bytes("a/b.txt", b"hello")
    assert store.exists("a/b.txt") is True
    assert store.read_bytes("a/b.txt") == b"hello"


def test_text_helpers(tmp_path):
    store = LocalSotStore(tmp_path / "SOT")
    write_text(store, "note.txt", "Miến Điện")
    assert read_text(store, "note.txt") == "Miến Điện"


def test_list_version_dirs_only_matches_version_folders(tmp_path):
    store = LocalSotStore(tmp_path / "SOT")
    store.write_bytes("Ver1_18072026/x", b"1")
    store.write_bytes("Ver2_19072026/x", b"1")
    store.write_bytes("junk/x", b"1")
    store.write_bytes("LATEST.json", b"{}")
    assert store.list_version_dirs() == ["Ver1_18072026", "Ver2_19072026"]


def test_read_only_store_refuses_write(tmp_path):
    store = LocalSotStore(tmp_path / "SOT", read_only=True)
    with pytest.raises(SotReadOnlyError):
        store.write_bytes("x.txt", b"nope")


def test_path_traversal_rejected(tmp_path):
    store = LocalSotStore(tmp_path / "SOT")
    with pytest.raises(ValueError):
        store.read_bytes("../escape.txt")
    with pytest.raises(ValueError):
        store.write_bytes("../../etc/passwd", b"x")


def test_gdriveStore_sameFolderLookedUpTwice_asksDriveOnce():
    """Trang SOT tra `SOT/` nhiều lần trong một lượt; mỗi lần là một lượt gọi Drive."""
    from types import SimpleNamespace

    from app.sot.store import GDriveSotStore

    da_hoi = []

    def _get_folder_id(ten, cha):
        da_hoi.append(ten)
        return None if ten == "thieu" else f"id-{ten}"

    client = SimpleNamespace(root_folder_id="goc", _get_folder_id=_get_folder_id)
    store = GDriveSotStore()
    assert store._find_folder_id(client, "SOT/Ver1") == "id-Ver1"
    assert store._find_folder_id(client, "SOT/Ver1") == "id-Ver1"
    assert store._find_folder_id(client, "SOT/Ver2") == "id-Ver2"
    assert da_hoi == ["SOT", "Ver1", "Ver2"]

    # Không có thì không nhớ: lần sau phải hỏi lại, thư mục có thể vừa được tạo.
    assert store._find_folder_id(client, "SOT/thieu") is None
    assert store._find_folder_id(client, "SOT/thieu") is None
    assert da_hoi.count("thieu") == 2
