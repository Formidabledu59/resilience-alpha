from conftest import striped_face

from recognizer import Recognizer


def test_enroll_and_recognize(tmp_path):
    rec = Recognizer(str(tmp_path / "model"))
    rec.enroll("alice", [striped_face("vertical", s) for s in range(5)])
    rec.enroll("bob", [striped_face("horizontal", s) for s in range(100, 105)])

    # Un visage du bon type est reconnu pour le bon identifiant
    assert rec.recognize("alice", striped_face("vertical", 999)) is True
    # Le visage d'alice n'est pas reconnu comme bob (label différent)
    assert rec.recognize("bob", striped_face("vertical", 999)) is False
    # Un identifiant inconnu n'est jamais reconnu
    assert rec.recognize("eve", striped_face("vertical", 999)) is False


def test_threshold_rejects_distant_match(tmp_path):
    # Seuil très bas : même le bon identifiant est refusé si la distance dépasse le seuil
    rec = Recognizer(str(tmp_path / "model"), threshold=0.1)
    rec.enroll("alice", [striped_face("vertical", s) for s in range(5)])
    assert rec.recognize("alice", striped_face("vertical", 42)) is False


def test_revoke_removes_user(tmp_path):
    rec = Recognizer(str(tmp_path / "model"))
    rec.enroll("alice", [striped_face("vertical", s) for s in range(5)])
    assert "alice" in rec.enrolled_users()
    rec.revoke("alice")
    assert rec.enrolled_users() == []
    assert rec.recognize("alice", striped_face("vertical", 1)) is False


def test_persistence_across_instances(tmp_path):
    rec = Recognizer(str(tmp_path / "model"))
    rec.enroll("alice", [striped_face("vertical", s) for s in range(5)])
    # Une nouvelle instance recharge le modèle depuis le disque
    rec2 = Recognizer(str(tmp_path / "model"))
    assert rec2.enrolled_users() == ["alice"]
    assert rec2.recognize("alice", striped_face("vertical", 7)) is True
