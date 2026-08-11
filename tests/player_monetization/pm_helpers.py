"""Shared factories for player_monetization tests. All synthetic, no live data."""
from operation.player_monetization.models import (
    PlayerProfile, PlayerSegment, PlayerLearningRecord,
)
from operation.player_monetization.events.collector import SyntheticProvider


def profile(user_id="u1", country="US", level=15, sessions=6,
            play_sec=1200, ad_req=30, ad_show=25, ad_comp=22,
            ad_rev=0.8, reward_show=20, reward_req=25,
            fails=2, levels=15, days=8, active=True) -> PlayerProfile:
    rr = reward_req
    return PlayerProfile(
        user_id=user_id, country=country, level=level,
        session_count=sessions, total_play_time_sec=play_sec,
        total_ad_requests=ad_req, total_ad_shows=ad_show,
        total_ad_completions=ad_comp, total_ad_revenue=ad_rev,
        reward_accept_rate=round(reward_show/rr, 4) if rr else 0.0,
        avg_session_sec=round(play_sec/sessions, 1) if sessions else 0.0,
        fail_rate=round(fails/levels, 4) if levels else 0.0,
        days_active=days, active=active)


def high_value_profile(uid="hv1"):
    return profile(uid, sessions=8, level=25, ad_rev=2.0, ad_show=40,
                   ad_req=50, reward_show=40, reward_req=45, levels=30)


def casual_profile(uid="c1"):
    return profile(uid, sessions=2, level=5, ad_rev=0.1, ad_show=3,
                   ad_req=5, reward_show=2, reward_req=3, days=2, levels=4)


def churn_profile(uid="at1"):
    return profile(uid, sessions=10, level=15, ad_rev=0.2, fails=8, levels=10,
                   active=False)


def new_profile(uid="n1"):
    return profile(uid, sessions=1, level=3, ad_rev=0.0, ad_show=0,
                   ad_req=1, reward_show=0, reward_req=1, days=1, levels=2,
                   play_sec=120)


def power_profile(uid="pw1"):
    return profile(uid, sessions=15, level=35, play_sec=5000, ad_rev=1.0,
                   ad_show=20, ad_req=30, levels=40)


def segment(uid="u1", seg="high_value_ad_player", score=85, risk=0.1,
            tol="high", conf=0.9):
    return PlayerSegment(user_id=uid, segment=seg, value_score=score,
                         churn_risk=risk, ad_tolerance=tol, confidence=conf)


def events_for_profiles(profiles: list) -> list:
    """Generate synthetic events for a list of PlayerProfile objects."""
    all_ev = []
    for p in profiles:
        s = SyntheticProvider()
        all_ev.extend(s.one_user(
            p.user_id, p.country, p.level, p.session_count,
            p.total_play_time_sec, p.total_ad_requests,
            p.total_ad_shows, p.total_ad_revenue))
    return all_ev
