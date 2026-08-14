from foundation.sources.census_asec import asec_archive_url


def test_asec_archive_url_2025():
    assert asec_archive_url(2025) == (
        "https://www2.census.gov/programs-surveys/cps/datasets/2025/march/asecpub25csv.zip"
    )
