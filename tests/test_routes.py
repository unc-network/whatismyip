import pytest

from whatismyip import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def test_metrics_route_is_public(client, monkeypatch):
    monkeypatch.setattr(
        "whatismyip.get_metrics_dashboard",
        lambda: {
            "window_days": 30,
            "total_hostinfo": 0,
            "total_campus": 0,
            "total_remote": 0,
            "daily_series": [],
            "daily_max": 0,
            "ip_versions": [],
            "isp_breakdown": [],
            "country_breakdown": [],
            "campus_breakdown": [],
            "purpose_breakdown": [],
        },
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert b"Usage Metrics" in response.data


def test_sitemap_includes_metrics(client):
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert b"https://whatismyip.unc.edu/metrics" in response.data


@pytest.mark.parametrize(
    ("path", "canonical_url"),
    [
        ("/", "https://whatismyip.unc.edu"),
        ("/about", "https://whatismyip.unc.edu/about"),
        ("/faq", "https://whatismyip.unc.edu/faq"),
        ("/metrics", "https://whatismyip.unc.edu/metrics"),
    ],
)
def test_pages_use_canonical_urls_from_sitemap(
    client, monkeypatch, path, canonical_url
):
    monkeypatch.setitem(app.config, "SERVER_URL", "https://whatismyip.unc.edu")
    monkeypatch.setattr(
        "whatismyip.get_metrics_dashboard",
        lambda: {
            "window_days": 30,
            "total_hostinfo": 0,
            "total_campus": 0,
            "total_remote": 0,
            "daily_series": [],
            "daily_max": 0,
            "ip_versions": [],
            "isp_breakdown": [],
            "country_breakdown": [],
            "campus_breakdown": [],
            "purpose_breakdown": [],
        },
    )

    response = client.get(path)

    assert response.status_code == 200
    assert f'<link rel="canonical" href="{canonical_url}">'.encode() in response.data
