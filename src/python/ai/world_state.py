def build_fsm_world_state(ai_p, opp_p) -> dict:
    dx = abs(ai_p.x - opp_p.x)
    dy = abs(ai_p.y - opp_p.y)
    # Chebyshev distance：X/Y 都必須進入閾值才算「夠近」
    dist = max(dx, dy)
    return {
        "dist":          dist,
        "dist_x":        dx,
        "dist_y":        dy,
        "facing_toward": (ai_p.facing_right and opp_p.x > ai_p.x) or
                         (not ai_p.facing_right and opp_p.x < ai_p.x),
        "self_hp":       ai_p.hp,
        "self_mp":       ai_p.mp,
        "self_airborne": ai_p.z > 0,
        "opp_state":     opp_p.state,
        "opp_airborne":  opp_p.z > 0,
    }


def build_pattern_world_state(ai_p, opp_p) -> dict:
    dx = abs(ai_p.x - opp_p.x)
    dy = abs(ai_p.y - opp_p.y)
    dist = max(dx, dy)
    opp_moving_toward = (
        (opp_p.vx > 0 and opp_p.x < ai_p.x) or
        (opp_p.vx < 0 and opp_p.x > ai_p.x)
    )
    return {
        "dist":          dist,
        "dist_x":        dx,
        "dist_y":        dy,
        "self_hp":       ai_p.hp,
        "self_mp":       ai_p.mp,
        "self_airborne": ai_p.z > 0,
        "opp_state":     opp_p.state,
        "opp_vx_toward": opp_moving_toward,
        "opp_airborne":  opp_p.z > 0,
    }
