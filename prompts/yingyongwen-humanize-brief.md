# Humanize 上游 brief · 高考英语应用文课堂

供 `humanize_ppt.py --source yingyongwen-source.md` 时使用。在源稿**开头**粘贴本段，使 AST 面向**学生投影**而非 Agent 开发者。

## Deck Brief（覆盖默认推断）

- **Audience**：高三学生（教室后排投影可读）
- **Initial State**：知道题目，但审题不准、理由空泛、句式单一
- **Desired State**：能三元审题、PEEL 成段、背诵本题句型、完成当堂迁移
- **Core Tension**：备课资料很全，但一页塞太多反而看不清、记不住
- **Success Criteria**：每页只完成一件事（one_thing）；学生屏不出现教师操作/时长/引导语

## AST 模块映射（6 宏页 → Architecture V1 70min 填槽）

| Humanize role | 应用文模块 | one_thing 示例 |
|---------------|-----------|----------------|
| hook | A1 导入 · 真题 | 进入情境，知道考什么题型 |
| context | A2–A3 情境/快思 | 读懂任务与 James 交际对象 |
| tension | B 审题 + C 思维 + Stage1 补充 | 意识到易错点，想写对 |
| method | D PEEL + 三版范文 | 看到 PEEL 路径与升级差异 |
| proof | E Stage3 句型词块 | 相信句型能直接套用 |
| takeaway | F 训练 + G 小结 | 带走高分公式，能当堂练 |

## slide_plan 要求

- 宏页 **6 条**即可（S01–S06）；**不要**把 export 全文塞进 `visible_content`
- 下游 `build_classroom_html_deck.py` 按 Architecture V1 **70min** 拆页填完整内容
- `speaker_intent` 写**教师讲法**，不写入学生投影 HTML

## 渲染下游

- Plan B HTML：`scripts/build_classroom_html_deck.py`（ecc-frontend-slides 风格）
- Plan A pptx：`one_click_classroom_ppt.py`（不变）
