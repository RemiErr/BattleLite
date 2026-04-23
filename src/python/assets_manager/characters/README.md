# 角色資源模組說明

`characters/` 目錄存放每個角色的 Python 類別，負責 Sprite 動畫與判定框定義。
底層由 `base_character.py` 提供共用基礎設施，子類別只需填入各自的數值。

---

## 目錄結構

```
assets_manager/
├── base_character.py        # BaseCharacter、HitboxDef 定義
└── characters/
    ├── README.md            # 本文件
    ├── knight.py            # 騎士
    └── (mage.py, ...)       # 其他角色
```

---

## 核心類別

### `HitboxDef`

```python
@dataclass
class HitboxDef:
    ox: int   # 框左上角相對 Sprite 中心的水平偏移（向右為正）
    oy: int   # 框左上角相對 Sprite 中心的垂直偏移（向下為正）
    w:  int   # 框寬（px）
    h:  int   # 框高（px）
```

**座標系統**：

```
    Sprite 中心 (0, 0)
ox 負值 ←─── 0 ───→ ox 正值
            │
            oy 正值 
```

**左右翻轉規則**：判定框定義以 **sheet 預設朝向** 為基準。
呼叫 `to_screen_rect(cx, cy, facing_right)` 時，若 `facing_right=True`，
框會自動水平鏡像，不需要為兩個方向各寫一份。

```
facing_right=False（預設朝向）    facing_right=True（鏡像）
  ┌──────┐                            ┌──────┐
  │ hurt │ 身體                  身體  │ hurt │
  └──────┘                            └──────┘
┌────┐                                      ┌────┐
│hit │ 攻擊（前方）               攻擊（前方）│hit │
└────┘                                      └────┘
```

---

## 判定框類型

| 屬性         | 字典 key     | Debug 顯示顏色 | 用途                                                      |
| ------------ | ------------ | -------------- | --------------------------------------------------------- |
| `hurt_boxes` | state（int） | 綠色           | 角色「被打到」的身體範圍                                  |
| `hit_boxes`  | state（int） | 紅色           | 攻擊動作「可命中敵人」的範圍；`None` 表示此狀態不造成傷害 |

**觸發條件（視覺語意）：紅框與敵人綠框重疊時觸發命中。**

Rust 碰撞公式為 `dx < atk_half_w + CHAR_WIDTH/2`，其中 `CHAR_WIDTH/2 = 15px` 代表受害者身體半寬補正。
換句話說：紅框邊緣需真正進入敵人身體（綠框）約 15px 才觸發；若紅框只是「剛剛碰到」綠框外緣，尚未判定為命中。
若想讓「恰好碰到就命中」，可將 `hit_box.w` 再加大約 30px（`CHAR_WIDTH`）。

---

## 新增角色步驟

### 1. 建立類別檔案

```python
# characters/mage.py
import os
import pygame
from src.python.assets_manager.base_character import BaseCharacter, HitboxDef

_SHEET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "src", "assets", "char", "mage", "sprite-sheet-W-H.png"
)

_FRAME_W = ???   # 每幀寬（px）
_FRAME_H = ???   # 每幀高（px）

_STATE_ROWS = [
    # (state, row, num_frames, loop, speed)
    (0, 0, 4, True,  6),   # IDLE
    (1, 1, 6, True,  6),   # WALK
    (2, 2, 5, False, 4),   # ATTACK
    (4, 3, 6, False, 4),   # SKILL
    (3, 4, 4, False, 4),   # HURT
]

STATE_IDLE, STATE_WALK, STATE_ATTACK, STATE_HURT, STATE_SKILL = 0, 1, 2, 3, 4

class Mage(BaseCharacter):
    def __init__(self):
        super().__init__("Mage")
        self.load_sheet(os.path.normpath(_SHEET_PATH), _FRAME_W, _FRAME_H, _STATE_ROWS)

        _body = HitboxDef(ox=???, oy=???, w=???, h=???)
        self.hurt_boxes = {
            STATE_IDLE:   _body,
            STATE_WALK:   _body,
            STATE_ATTACK: _body,
            STATE_SKILL:  _body,
            STATE_HURT:   HitboxDef(...),
        }
        self.hit_boxes = {
            STATE_IDLE:   None,
            STATE_WALK:   None,
            STATE_ATTACK: HitboxDef(...),
            STATE_SKILL:  HitboxDef(...),
            STATE_HURT:   None,
        }

    def get_sprite(self, state, elapsed_frames, facing_right=True):
        surf = self.get_sprite_rect(state, elapsed_frames)
        if surf is None:
            surf = self.get_sprite_rect(0, 0)
        assert surf is not None
        # 依 sheet 預設朝向決定是否翻轉
        if facing_right:                          # sheet 朝左時翻轉
            return pygame.transform.flip(surf, True, False)
        return surf
```

### 2. 量測判定框數值

啟動遊戲後按 **F1** 開啟 Debug Overlay，可看到綠框（hurt）和紅框（hit）疊在 Sprite 上。
對照畫面調整角色數值 `ox / oy / w / h` (e.g. `knight.py`)直到框覆蓋正確位置。

```
# 每個 HitboxDef 只有 4 個數字可調：
HitboxDef(ox=-73, oy=-51, w=67, h=98)
#             ↑       ↑     ↑     ↑
#           左偏移  上偏移   寬    高
```

**量測方式（不用 Debug 模式）**：

1. 用圖片編輯器（GIMP、Photoshop、Aseprite）開啟 sprite sheet。
2. 在單幀（frame_w × frame_h）中，框出角色身體的矩形，記錄：
   - 左邊距 `x1`、上邊距 `y1`、右邊距 `x2`、下邊距 `y2`（相對單幀左上角）
3. 換算為相對 Sprite 中心的偏移：
   ```
   center_x = frame_w // 2
   center_y = frame_h // 2
   
   ox = x1 - center_x
   oy = y1 - center_y
   w  = x2 - x1
   h  = y2 - y1
   ```

### 3. 翻轉方向判斷

| Sheet 預設朝向 | `get_sprite` 中翻轉條件     |
| -------------- | --------------------------- |
| 朝左（常見）   | `if facing_right: flip`     |
| 朝右           | `if not facing_right: flip` |

---

## Knight 判定框參考值

Sprite 尺寸：183 × 123 px，中心 (91, 61)，sheet 預設**朝左**。

```python
# hurt_box（一般站立/行走/攻擊狀態）
HitboxDef(ox=-73, oy=-51, w=67, h=98)
# 對應 frame 絕對座標：x=18–85, y=10–108

# hurt_box（HURT 受擊狀態，身體略縮）
HitboxDef(ox=-60, oy=-40, w=55, h=80)

# hit_box（ATTACK：斬擊弧，Row1 幀2–3，朝左延伸）
HitboxDef(ox=-91, oy=-53, w=55, h=74)
# 對應 frame 絕對座標：x=0–55, y=8–82

# hit_box（SKILL：盾牌光暈，Row2 幀4–5）
HitboxDef(ox=-51, oy=-46, w=60, h=75)
# 對應 frame 絕對座標：x=40–100, y=15–90
```

---

## Debug 模式

遊戲中按 **F1** 切換 Debug Overlay：
- **綠色框**：`hurt_box`（被命中範圍）
- **紅色框**：`hit_box`（攻擊傷害範圍）；無攻擊的狀態不顯示

判定框僅為視覺參考，實際遊戲物理碰撞由 Rust 核心（`src/rust_core/src/lib.rs`）的固定點座標計算負責。
