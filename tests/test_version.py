import re

import gtfs_rt_kit


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-.]?(?:a|b|rc|dev)\d+)?", gtfs_rt_kit.__version__)
