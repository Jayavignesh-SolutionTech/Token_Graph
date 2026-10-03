from tokenguard.sources import content_chars, project_name


def test_project_name_uses_git_root(tmp_path):
    repo = tmp_path / "my-repo"
    (repo / ".git").mkdir(parents=True)
    sub = repo / "packages" / "cli"
    sub.mkdir(parents=True)
    assert project_name(str(sub)) == "my-repo"


def test_project_name_falls_back_to_directory_name():
    assert project_name("C:\\nowhere\\that\\exists\\api-server") == "api-server"
    assert project_name(None) == "unknown"


def test_content_chars_handles_blocks():
    assert content_chars("abc") == 3
    assert content_chars([{"type": "text", "text": "abcd"}, {"type": "image"}]) == 4
    assert content_chars([{"type": "tool_result", "content": [{"type": "text", "text": "xy"}]}]) == 2
