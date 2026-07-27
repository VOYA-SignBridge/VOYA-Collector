"""Recovery behaviour of init_db().

These tests used to assert that a failed CSV->DB sync triggered
drop_all_tables(). That contract was itself the bug: init_db() runs on every
backend start and sync_missing_data_on_startup() returns False on ANY exception,
so a briefly locked CSV (they sit next to .lock files) was enough to drop users,
refresh_tokens, password_reset_tokens, training_jobs and training_metrics —
tables the CSVs cannot rebuild. The drop is now reserved for a schema that is
actually corrupt.
"""

from unittest.mock import patch

from app.db import init_db


@patch("app.db.sync_missing_data_on_startup")
@patch("app.storage.metadata_db.drop_all_tables")
@patch("app.storage.metadata_db.ensure_tables")
@patch("app.storage.metadata_db._column_exists")
def test_sync_failure_alone_never_drops_tables(mock_col, mock_ensure, mock_drop, mock_sync):
    """A failed sync with a healthy schema must leave the database untouched."""
    mock_col.return_value = True      # schema fine: samples.deleted_at present
    mock_sync.return_value = False    # but the CSV read failed

    result = init_db()

    # Reported as a failure...
    assert result is False
    # ...without destroying anything. This is the entire point of the fix.
    assert mock_drop.call_count == 0
    assert mock_ensure.call_count == 1
    # No pointless retry of the thing that just failed.
    assert mock_sync.call_count == 1


@patch("app.db.sync_missing_data_on_startup")
@patch("app.storage.metadata_db.drop_all_tables")
@patch("app.storage.metadata_db.ensure_tables")
@patch("app.storage.metadata_db._column_exists")
def test_corrupt_schema_still_rebuilds(mock_col, mock_ensure, mock_drop, mock_sync):
    """A genuinely corrupt schema still takes the drop-and-rebuild path."""
    mock_col.return_value = False     # samples.deleted_at missing
    mock_sync.side_effect = [True, True]

    result = init_db()

    assert result is True
    assert mock_drop.call_count == 1
    assert mock_ensure.call_count == 2   # initial + after the drop
    assert mock_sync.call_count == 2     # initial + re-seed


@patch("app.db.sync_missing_data_on_startup")
@patch("app.storage.metadata_db.drop_all_tables")
@patch("app.storage.metadata_db.ensure_tables")
@patch("app.storage.metadata_db._column_exists")
def test_corrupt_schema_rebuild_failure_reports_false(mock_col, mock_ensure, mock_drop, mock_sync):
    """If the rebuild's re-seed also fails, init_db reports failure."""
    mock_col.return_value = False
    mock_sync.side_effect = [True, False]

    result = init_db()

    assert result is False
    assert mock_drop.call_count == 1
    assert mock_ensure.call_count == 2
    assert mock_sync.call_count == 2


@patch("app.db.sync_missing_data_on_startup")
@patch("app.storage.metadata_db.drop_all_tables")
@patch("app.storage.metadata_db.ensure_tables")
@patch("app.storage.metadata_db._column_exists")
def test_healthy_startup_is_a_no_op(mock_col, mock_ensure, mock_drop, mock_sync):
    """The normal path: schema fine, sync fine, nothing dropped."""
    mock_col.return_value = True
    mock_sync.return_value = True

    assert init_db() is True
    assert mock_drop.call_count == 0
    assert mock_ensure.call_count == 1
    assert mock_sync.call_count == 1
