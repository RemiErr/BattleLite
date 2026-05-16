use crate::player::Player;

const WORLD_X_MIN: i32 = 0;
const WORLD_X_MAX: i32 = 3_072_000;
const WORLD_Y_MIN: i32 = 250_000;
const WORLD_Y_MAX: i32 = 520_000;

pub(crate) fn clamp_to_world(players: &mut Vec<Player>) {
    for p in players.iter_mut() {
        if p.x < WORLD_X_MIN      { p.x = WORLD_X_MIN; p.vx = 0; }
        else if p.x > WORLD_X_MAX { p.x = WORLD_X_MAX; p.vx = 0; }
        if p.y < WORLD_Y_MIN      { p.y = WORLD_Y_MIN; p.vy = 0; }
        else if p.y > WORLD_Y_MAX { p.y = WORLD_Y_MAX; p.vy = 0; }
    }
}
