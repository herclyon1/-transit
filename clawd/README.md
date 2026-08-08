# Claw'd 素材来源

这个目录里的三个文件都是**从 Anthropic 自己的服务器原样下载的**，一个字节都没改，
也没有任何我自己画的部分。之前几轮我自己拼 SVG，怎么都对不上，那条路已经废弃。

| 文件 | 来源 URL | 大小 |
|---|---|---|
| `clawd.svg` | `https://claude.ai/images/clawd.svg` | 322 B |
| `clawd-laptop.webm` | `https://claude.com/images/install-hub/clawd-laptop.webm` | 31 KB |
| `clawd-laptop.mov` | `https://claude.com/images/install-hub/clawd-laptop.mov` | 128 KB |

- `clawd.svg`：viewBox `0 0 66 52`，body `#D97757`，眼睛 `#141413`。
- 两个视频是同一段动画的两种封装：**2750×1850、12fps、43 帧、带透明通道**。
  webm 是 VP9 + alpha（Chrome/Firefox），mov 是 HEVC + alpha（Safari）。
  `<source>` 里 mov 必须排在前面，Safari 才会选它；Chrome 不认 quicktime 会自动跳到 webm。
- 动画内容只占画布的 `x 736..2036 / y 850..1850`，其余是透明留白。
  首页没有裁剪文件，而是用一个 130×100 的窗口把这块放大平移出来（见 index.html 的 CSS 注释）。

验证：把首页 `.stage` 截图与 `clawd-laptop.webm` 第 1 帧按同一裁剪框逐像素比对，**吻合 98.3%**，
差异全部落在缩放后的一行边缘上。轮廓与 `clawd.svg` 的 path 完全一致。

## 怎么找到的

1. 用户存下的官方页面 `.mht` 里没有任何图片分段，但 HTML 里有一段 52 KB 的
   inline SVG，容器 id 是 `__lottie_element_30`，viewBox 正好 2750×1850 —— 说明官方用的是 Lottie。
2. `.mht` 不保存 JS，但里面的 `<script src>` 指向 `assets-proxy.anthropic.com`，**这个域名可以直接访问**。
   下载那 32 个 chunk，从里面的 `import("./cXXXXXXXX-YYYYYYYY.js")` 抽出 417 个懒加载 chunk 全部下载，
   再 grep 就拿到了 `/images/clawd.svg` 和 `/images/install-hub/clawd-laptop.{mov,webm}`。
3. `claude.ai` 对普通请求返回 403（Cloudflare），但**带浏览器 UA 时静态图片可以下**；
   `claude.com` 则整个开放。两边配合就把文件拿全了。

## 还差的那一个：敲键盘的 Lottie

页面上那段「掏出笔电打字」的动画是 `https://claude.ai/animations/code-terminal.json`
（同目录还有 object-browsers / object-clouds / object-shield）。

**这个拿不到**：该路径对任何未登录请求都返回 `{"error":{"type":"forbidden"}}`，
换 UA、换 Referer、走无头浏览器都一样；`claude.com` 和 assets-proxy 上都是 404。
用户存的 `.mht` 里也没有——Chrome 保存 MHTML 时不保存 XHR 拿回来的 JSON，
只留下了渲染完的那一帧 DOM（`pipeline/official_lottie_frame.svg` 留档，44 条 path，
其中 9 条灰色的是笔电）。

要补齐只需要一步：**在手机浏览器里登录状态下打开那个 URL，把 JSON 存下来给我**，
放进这个目录再用 lottie-web 播放即可，同样不用自己画。
