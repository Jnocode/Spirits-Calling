# 藍圖連線教學 (中文介面版)

從您的截圖來看，您目前是點擊了左邊的列表。
**請先雙擊左邊的 "EventGraph" (事件圖表)，確保中間出現充滿格線的「大黑板」。**
所有的「右鍵」都要點在這個**大黑板 (Grid)** 的空白處。

即便介面是中文，您通常還是可以輸入英文搜尋，但以下提供中文名稱對照：

---

## 任務 1: 開啟滑鼠 (在 `BP_SpiritController`)

1. **確保您在這個藍圖的「Event Graph (事件圖表)」分頁中。**
2. 找到紅色的 **Event BeginPlay (事件开始运行)** 節點。
3. 在空白處右鍵搜尋：**"Add Mapping Context" (添加映射上下文)**。
    * **連線**：把 `Event BeginPlay` 的白色箭頭 -> 連到這個節點。
    * **Target (目标)**：從藍色針腳拉出 -> 搜尋 **"Get Local Player Subsystem" (获取本地玩家子系统)** -> 選擇 **EnhancedInputLocalPlayerSubsystem**。
    * **Mapping Context**: 選 **`IMC_Spirit`**。
4. 右鍵搜尋：**"Set Show Mouse Cursor" (设置显示鼠标光标)**。
    * **連線**：串接上去。
    * **打勾**：把那個勾勾選起來 (代表 True)。
5. 右鍵搜尋：**"Set Input Mode Game and UI" (设置输入模式游戏和UI)**。
    * **連線**：串接上去。
    * **Player Controller**: 搜尋 "Self" (自身) -> **Get Reference to Self (获取自身的引用)**。
6. 按左上角的 **Compile (编译)**。

---

## 任務 2: RTS 相機移動 (在 `BP_SpiritPawn`)

### **[推薦] 超級簡化版 (不需要算數學！)**

如果您覺得數學連線太麻煩，請用這個方法：

1. **添加組件**：
    * 在 `BP_SpiritPawn` 的左上角 **Components** 面板，點擊綠色的 **+ Add**。
    * 搜尋 **"Floating Pawn Movement" (浮动 Pawn 移动)** 並添加它。
    * (選中它，右邊 Details 面板可以調整 Max Speed 來改變速度，例如設為 2000)。

2. **超簡單連線**：
    * 右鍵搜尋：**"IA_RTS_Move"**。
    * 右鍵搜尋：**"Add Movement Input" (添加移动输入)**。(注意：不要選到 Add Actor Local Offset)
    * **X (前後)**：
        * 右鍵搜尋：**"Get Actor Forward Vector"**。
        * 連線：`Forward Vector` -> **World Direction**。
        * 連線：`Break Vector 2D` 的 **X** -> **Scale Value**。
        * 連線：`IA_RTS_Move` (Triggered) -> `Add Movement Input` (Exec)。
    * **Y (左右)**：
        * 複製一個 `Add Movement Input`。
        * 右鍵搜尋：**"Get Actor Right Vector"**。
        * 連線：`Right Vector` -> **World Direction**。
        * 連線：`Break Vector 2D` 的 **Y** -> **Scale Value**。
        * 串聯執行：上一個 `Add Movement Input` 連過來。

**(如果您用了這個方法，下面的「手動數學版」可以跳過！)**

---

### **[備用] 手動數學版 (原本的方法)**

1. 打開 `BP_SpiritPawn` -> 切換到 **Event Graph**。
2. 右鍵搜尋：**"IA_RTS_Move"** (這個名稱是我們自訂的，所以是英文)。
3. 右鍵搜尋：**"Add Actor Local Offset" (添加 Actor 局部偏移)**。
4. **拆分方向**：
    * 從 `IA_RTS_Move` 的藍色 **Action Value** 拉出來 -> 搜尋 **"Break Vector 2D" (中断 Vector 2D)**。
    * 現在您有 X 和 Y。
5. **前後移動 (X) 的連線細節**：
    * **獲取方向**：右鍵搜尋 **"Get Actor Forward Vector" (获取 Actor 向前向量)**。(這是一個黃色針腳)
    * **計算移動量**：
        1. 從 Forward Vector 的黃色針腳拉出來 -> 輸入 `*` -> 選擇 **"Multiply" (乘法)**。
        2. 把 **Break Vector 2D** 的 **X** (綠色針腳) 連到這個乘法節點的下面那個針腳。
           *(注意：此時節點會變成 `Vector * Float`，黃色 x 綠色)*
        3. 從這個乘法節點右邊再一次拉出來 -> 輸入 `*` -> 選擇 **"Multiply"**。
        4. 在下面那個格子輸入 **10.0** (這是速度)。
    * **應用移動**：
        1. 把最後的黃色針腳連到 `Add Actor Local Offset` 的 **Delta Location**。
        2. 把紅色 `IA_RTS_Move` 的 **Triggered** 箭頭連到 `Add Actor Local Offset` 的左邊箭頭。

6. **左右移動 (Y) (這一步也要做！)**：
    * **複製**：選取剛才做的 `Add Actor Local Offset` 字眼，Ctrl+C, Ctrl+V 複製一個新的。
    * **獲取方向**：右鍵搜尋 **"Get Actor Right Vector" (获取 Actor 向右向量)**。
    * **計算**：一樣做 `Right Vector` *`Y (來自 Break Vector)`* `10.0`。
    * **連線**：
        1. 把上一個 `Add Actor Local Offset` 的右邊箭頭，連到這一個新的 `Add Actor Local Offset` 的左邊箭頭 (串聯執行)。
        2. 把計算結果連到這個新的 **Delta Location**。

---

## 任務 3: 點擊附身 (在 `BP_SpiritController`)

1. 回到 `BP_SpiritController`。
2. 右鍵搜尋：**"IA_Select"**。
3. 右鍵搜尋：**"Get Hit Result Under Cursor by Channel" (按通道获取光标下的命中结果)**。
    * Trace Channel (追踪通道) 選 **Visibility (可见性)**。
4. 連線：`IA_Select` -> `Get Hit Result...`。
5. 右鍵搜尋：**"Break Hit Result" (中断命中结果)**。
6. 檢查點到誰：
    * 從 **Hit Actor (命中 Actor)** 拉出來 -> 搜尋 **"Cast To BP_UnitBase" (投射到 BP_UnitBase)**。
7. 附身：
    * 從 Cast 成功的箭頭拉出來 -> 搜尋 **"Possess" (拥有 / 附身)**。
    * **Target (目标)**：搜尋 "Self" (自身)。
    * **Pawn**: 把 Cast 節點右邊藍色的 "As BP Unit Base" 連過來。

---

**先試著做「任務 1」，如果滑鼠出來了，就代表您成功了！**
