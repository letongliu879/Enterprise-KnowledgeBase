from reality_rag_persistence.ingestion_monitor import IngestionMonitorStore


def test_monitor_store_persists_run_and_events(tmp_path):
    store = IngestionMonitorStore(tmp_path)
    run = store.create_run(
        run_id="monitor-1",
        collection_id="col-1",
        index_version="col-1-v1",
        concurrency=4,
        source_files=["E:/doc-a.docx"],
    )
    assert run["run_id"] == "monitor-1"

    store.append_event(
        "monitor-1",
        lane_id=0,
        event_type="lane.assigned",
        phase="queue",
        message="Lane 1 picked up doc-a.docx",
    )
    loaded = store.get_run("monitor-1")
    events = store.get_events("monitor-1")

    assert loaded is not None
    assert loaded["last_seq"] == 1
    assert len(events) == 1
    assert events[0]["type"] == "lane.assigned"
