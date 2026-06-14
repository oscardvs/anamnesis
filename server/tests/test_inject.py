import subprocess

from anamnesis.inject import _normalize_remote, resolve_project_key


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_normalize_remote_scp_and_https_and_path():
    assert (
        _normalize_remote("git@github.com:oscardvs/anamnesis.git")
        == "github.com/oscardvs/anamnesis"
    )
    assert (
        _normalize_remote("https://github.com/oscardvs/Anamnesis.git")
        == "github.com/oscardvs/anamnesis"
    )
    assert _normalize_remote("/home/odesha/anamnesis-memory.git") == "/home/odesha/anamnesis-memory"


def test_resolve_project_key_prefers_git_remote(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "remote", "add", "origin", "git@github.com:oscardvs/anamnesis.git")
    assert resolve_project_key(tmp_path) == "github.com/oscardvs/anamnesis"


def test_resolve_project_key_falls_back_to_repo_dirname(tmp_path):
    repo = tmp_path / "MyRepo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    assert resolve_project_key(repo) == "myrepo"


def test_resolve_project_key_non_git_uses_cwd_basename(tmp_path):
    d = tmp_path / "PlainDir"
    d.mkdir()
    assert resolve_project_key(d) == "plaindir"
