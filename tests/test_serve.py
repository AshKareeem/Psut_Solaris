import pytest

from scripts.serve import parse_mission

GOOD = dict(lat=-89.7786, lon=-155.7256, terrain="20m", mast_m=2, start_utc="2027-03-01T06", days=14, e_max_Wh=700,
            e_min_Wh=140, p_panel_W=200, p_load_W=50, earth_margin_deg=0)


def test_a_good_mission_comes_back_typed():
    m = parse_mission({**GOOD, "mast_m": "5", "start_utc": "2027-03-01T06"})
    assert m["mast_m"] == 5.0 and m["start_utc"] == "2027-03-01T06" and m["terrain"] == "20m"


@pytest.mark.parametrize("change, reason", [
    ({"lat": -60}, "latitude"),
    ({"terrain": "80m"}, "terrain"),
    ({"mast_m": -1}, "height"),
    ({"days": 0}, "mission length"),
    ({"e_min_Wh": 800}, "reserve"),
    ({"p_load_W": -5}, "negative"),
    ({"earth_margin_deg": 20}, "Earth margin"),
    ({"start_utc": "2051-01-01T00"}, "DE421"),
])
def test_a_bad_mission_is_refused_with_the_reason(change, reason):
    with pytest.raises(ValueError, match=reason):
        parse_mission({**GOOD, **change})


def test_a_missing_field_is_named():
    body = dict(GOOD)
    del body["p_panel_W"]
    with pytest.raises(ValueError, match="missing: p_panel_W"):
        parse_mission(body)


def test_a_malformed_landing_hour_is_refused():
    with pytest.raises(ValueError):
        parse_mission({**GOOD, "start_utc": "next tuesday"})


def test_the_published_site_may_call_the_mission_api_and_no_other_origin(tmp_path):
    """GitHub Pages calls /api/mission through the tunnel (scripts/start_public.py); only that origin is allowed."""
    import http.client
    import threading
    from functools import partial
    from http.server import ThreadingHTTPServer
    from scripts.serve import PAGES_ORIGIN, Handler
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(tmp_path)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        def ask(method, origin, body=None):
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1])
            c.request(method, "/api/mission", body=body, headers={"Origin": origin, "Content-Type": "application/json"})
            r = c.getresponse(); r.read(); return r
        pre = ask("OPTIONS", PAGES_ORIGIN)
        assert pre.status == 204 and pre.getheader("Access-Control-Allow-Origin") == PAGES_ORIGIN
        bad = ask("POST", PAGES_ORIGIN, body=b"{}")                  # missing fields: a 400 the page can read
        assert bad.status == 400 and bad.getheader("Access-Control-Allow-Origin") == PAGES_ORIGIN
        assert ask("OPTIONS", "https://example.com").getheader("Access-Control-Allow-Origin") is None
    finally:
        srv.shutdown()
