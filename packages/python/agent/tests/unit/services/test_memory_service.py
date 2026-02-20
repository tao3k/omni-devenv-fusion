from pathlib import Path

from omni.agent.services import memory as memory_service


class _DummyEncoder:
    def __init__(self, dimension: int):
        self._dimension = dimension

    def encode(self, _text: str) -> list[float]:
        return [0.0] * self._dimension


class _DummyStore:
    def __init__(self):
        self.saved_paths: list[str] = []
        self.saved_q_paths: list[str] = []
        self.stored_episodes: list[object] = []

    def store(self, episode: object) -> str:
        self.stored_episodes.append(episode)
        return "ok"

    def save(self, path: str) -> None:
        self.saved_paths.append(path)

    def save_q_table(self, path: str) -> None:
        self.saved_q_paths.append(path)

    def load(self, _path: str) -> None:
        return None

    def load_q_table(self, _path: str) -> None:
        return None

    def update_q(self, _episode_id: str, reward: float) -> float:
        return reward

    def get(self, _episode_id: str):
        return None

    def get_all(self):
        return []

    def len(self) -> int:
        return len(self.stored_episodes)

    def is_empty(self) -> bool:
        return not self.stored_episodes

    def recall_with_embedding(self, _embedding: list[float], _k: int):
        return []

    def two_phase_recall_with_embedding(
        self, _embedding: list[float], _k1: int, _k2: int, _qw: float
    ):
        return []

    def multi_hop_recall_with_embeddings(self, _embeddings: list[list[float]], _k: int, _qw: float):
        return []


def _patch_memory_omni(monkeypatch, store: _DummyStore, captured_cfg: dict[str, object]) -> None:
    class _FakeStoreConfig:
        def __init__(self, path: str, embedding_dim: int, table_name: str):
            captured_cfg["path"] = path
            captured_cfg["embedding_dim"] = embedding_dim
            captured_cfg["table_name"] = table_name

    class _FakeTwoPhaseConfig:
        def __init__(self, k1: int, k2: int, q_weight: float):
            self.k1 = k1
            self.k2 = k2
            setattr(self, "lambda", q_weight)

    monkeypatch.setattr(memory_service.omni, "PyStoreConfig", _FakeStoreConfig)
    monkeypatch.setattr(memory_service.omni, "PyTwoPhaseConfig", _FakeTwoPhaseConfig)
    monkeypatch.setattr(
        memory_service.omni, "create_intent_encoder", lambda dim: _DummyEncoder(dim)
    )
    monkeypatch.setattr(memory_service.omni, "create_q_table", lambda *_args: object())
    monkeypatch.setattr(memory_service.omni, "create_episode_store", lambda _cfg: store)
    monkeypatch.setattr(memory_service.omni, "create_two_phase_search", lambda *_args: object())
    monkeypatch.setattr(
        memory_service.omni,
        "create_episode_with_embedding",
        lambda episode_id, intent, experience, outcome, embedding: {
            "id": episode_id,
            "intent": intent,
            "experience": experience,
            "outcome": outcome,
            "embedding": embedding,
        },
    )


def test_memory_service_uses_configured_path_for_store(monkeypatch, tmp_path: Path) -> None:
    store = _DummyStore()
    captured_cfg: dict[str, object] = {}
    _patch_memory_omni(monkeypatch, store, captured_cfg)

    cfg = memory_service.MemoryConfig(
        path=str(tmp_path / "memory-root"),
        embedding_dim=16,
        table_name="episodes_a",
    )
    memory_service.MemoryService(cfg)

    assert captured_cfg["path"] == cfg.path
    assert captured_cfg["embedding_dim"] == cfg.embedding_dim
    assert captured_cfg["table_name"] == cfg.table_name


def test_store_episode_persists_state_to_table_scoped_files(monkeypatch, tmp_path: Path) -> None:
    store = _DummyStore()
    captured_cfg: dict[str, object] = {}
    _patch_memory_omni(monkeypatch, store, captured_cfg)
    monkeypatch.setattr(memory_service, "embed_text", lambda _text: [0.1, 0.2, 0.3, 0.4])

    cfg = memory_service.MemoryConfig(
        path=str(tmp_path / "state-root"),
        embedding_dim=4,
        table_name="episodes_b",
    )
    svc = memory_service.MemoryService(cfg)
    episode_id = svc.store_episode(
        intent="debug timeout",
        experience="increase timeout",
        outcome="success",
        episode_id="ep-fixed",
    )

    expected_episode_path = str(tmp_path / "state-root" / "episodes_b.episodes.json")
    expected_q_table_path = str(tmp_path / "state-root" / "episodes_b.q_table.json")

    assert episode_id == "ep-fixed"
    assert store.saved_paths == [expected_episode_path]
    assert store.saved_q_paths == [expected_q_table_path]
