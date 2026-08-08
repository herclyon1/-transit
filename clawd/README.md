# Claw'd 素材来源

这里的动画和静图都是**从 Anthropic 自己的服务器原样下载的**，一个字节都没改，
没有任何我自己画的部分。前面几轮我自己拼 SVG 怎么都对不上，那条路已经废弃。

| 文件 | 来源 URL | 大小 |
|---|---|---|
| `clawd-laptop.json` | `https://assets-proxy.anthropic.com/claude-ai/v2/assets/v1/c838f53ee-DqwARLA7.json` | 106 KB |
| `clawd.svg` | `https://claude.ai/images/clawd.svg` | 322 B |
| `lottie_light.min.js` | lottie-web 5.12.2（MIT），官方页面同款播放器 | 164 KB |

- `clawd-laptop.json`：Lottie 5.7.4，内部名 **`Clawd-Laptop`**，`2750×1850`，**12fps、43 帧**。
  这就是 claude.ai/code 上那段「掏出笔电、转身、打字、收起来」的动画本体。
- `clawd.svg`：viewBox `0 0 66 52`，body `#D97757`，眼睛 `#141413`。当播放器没加载出来时做兜底。
- 动画内容只占画布 `x 733..2437 / y 700..1850`（约 61.9% × 62.2%），其余是透明留白。
  首页没有改 JSON，而是用一个 178×120 的窗口把这块放大平移出来（见 index.html 的 CSS 注释）。
- 方向：笔电出在螃蟹**右侧**。这就是官方的样子——官方页面上包裹这个动画的
  三层 div 是 `relative h-0 …` / `pointer-events-auto` / `w-full h-full`，
  **没有任何水平翻转**，所以这里也不翻。

## 验收

把官方页面 `.mht` 里那一帧（即 claude.ai 自己渲染出来的 DOM）与本地播放的 43 帧
逐一按内容框归一化后比对：

- 最吻合帧 **99.59%**（第 2/3/41/42 帧，都是正面站立那一姿势）
- 内容框宽高比 官方 **1.502** vs 本地 **1.504**

## 怎么找到的

1. 用户存下的官方页面 `.mht` 里没有图片分段，但 HTML 里有一段 52 KB 的 inline SVG，
   容器 id 是 `__lottie_element_30`，viewBox 正好 `2750×1850` —— 说明官方用的是 Lottie。
2. `.mht` 不保存 JS，但 `<script src>` 指向 `assets-proxy.anthropic.com`，**这个域名可以直接访问**。
   下载那 32 个 chunk，从 `import("./cXXXXXXXX-YYYYYYYY.js")` 抽出懒加载 chunk 再下一轮，
   两层展开后共 966 个。
3. grep 到组件 `ClawdLaptopInner`，它 `import { c, l }` 自 `c11959232-Dz1wkkE8.js`，
   把 `l` 的定义挖出来就是**写死的 URL**：
   ```js
   Bh = "https://assets-proxy.anthropic.com/claude-ai/v2/assets/v1/c838f53ee-DqwARLA7.json"
   ```
   直接 curl 就下来了。

## 走过的两条弯路（留着免得再踩）

- `claude.com/images/install-hub/clawd-laptop.webm` / `.mov`（2750×1850、12fps、43 帧、带 alpha）
  也是官方文件，但**里面没有笔电**——43 帧全扫过，一个灰色像素都没有，
  只有螃蟹转身。名字里的 laptop 指的是「桌面端安装页」，不是道具。已从仓库移除。
- `claude.ai/animations/code-terminal.json` 内部名 `Object-CodeTerminal-lottie`，
  1200×1200、44 帧，是那个 `</>` 终端窗口图标，**不是螃蟹**。
  该路径对未登录请求返回 403，需要登录才能下。
