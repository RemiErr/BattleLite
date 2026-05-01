def build_fsm_world_state(ai_p, opp_p) -> dict:
    dist = abs(ai_p.x - opp_p.x)
    return {
        "dist":          dist,
        "facing_toward": (ai_p.facing_right and opp_p.x > ai_p.x) or
                         (not ai_p.facing_right and opp_p.x < ai_p.x),
        "self_hp":       ai_p.hp,
        "self_mp":       ai_p.mp,
        "self_airborne": ai_p.z > 0,
        "opp_state":     opp_p.state,
        "opp_airborne":  opp_p.z > 0,
    }


def build_pattern_world_state(ai_p, opp_p) -> dict:
    dist = abs(ai_p.x - opp_p.x)
    opp_moving_toward = (
        (opp_p.vx > 0 and opp_p.x < ai_p.x) or
        (opp_p.vx < 0 and opp_p.x > ai_p.x)
    )
    return {
        "dist":          dist,
        "self_hp":       ai_p.hp,
        "self_mp":       ai_p.mp,
        "self_airborne": ai_p.z > 0,
        "opp_state":     opp_p.state,
        "opp_vx_toward": opp_moving_toward,
        "opp_airborne":  opp_p.z > 0,
    }
