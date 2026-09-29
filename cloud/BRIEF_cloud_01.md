# 交底书 · 云端版第一版（P2）

> 编写日期：2026-09-29
> 执行者：codex
> 验收者：Hermes（独立实跑，不采信自述）
> 工作目录：`D:\AI输出的文件\project_ldsg_cloud\`

---

## 0. 先读这一段（重要，请照做）

这份交底书有明确的边界，**请严格遵守**：

1. **只做本任务描述的事，不做研究、不做扩展。** 架构已经定好（见第 2 节），不需要你重新设计。
2. **不要自己写测试脚本。** 第 8 节给了验证方法，按那个来。你若自写脚本卡住，那是你的脚本问题，不是项目问题。
3. **单个命令的运行时间上限 5 分钟。** 超过就放弃它、继续往下做，并在交付说明里注明「该命令超时未返回」。
4. **跑不通就如实报告跑不通。** 不要为了让它变绿而反复重跑或修改验证脚本。
5. **遇到无法解决的阻塞，停下来写清楚卡在哪**，不要自己想办法绕（尤其是绕开第 5 节的存储抽象层要求）。

---

## 1. 任务

把已经在本机跑通的「课程资料共享站」**重写为 Cloudflare 云端版本**，并在本地用 `wrangler dev` 跑通。

本机版（Python）已完成并通过实测，代码在 `D:\AI输出的文件\project_ldsg\`，**那是参考实现，不要修改它**。功能行为要与之保持一致。

**为什么是重写而不是搬运**：Cloudflare Workers 跑 JavaScript，不是 Python。所以要重写，但**逻辑、页面、文案都可以照搬**。

---

## 2. 已定的架构（不要改动）

| 项 | 决定 |
|---|---|
| 接口层 | Cloudflare **Workers**（JavaScript，ES Module 格式） |
| 元数据 | **D1**（SQLite 兼容） |
| 文件实体 | **R2**，但必须经过存储抽象层（见第 5 节） |
| 前端 | Worker 直接输出 HTML 字符串。**不要用 React、不要用 Vite、不要用 Pages、不要 npm 前端构建** |
| 第三方依赖 | **零**。只能用 Workers 运行时自带的能力（`fetch`、Web Crypto、`crypto.randomUUID` 等） |

**禁止事项：**
- 不要引入任何 npm 运行时依赖（devDependency 里的 wrangler 除外）
- 不要引入框架、打包器、模板引擎
- 不要用 `nodejs_compat` 以外的 Node API
- 不要把文件字节读进 Worker 内存再转发（见第 5 节说明）

---

## 3. 目录结构（按此创建）

```
D:\AI输出的文件\project_ldsg_cloud\
  wrangler.toml          配置（D1/R2 绑定、环境变量）
  package.json           只有 wrangler 作为 devDependency
  schema.sql             D1 建表语句
  src/
    index.js             入口：fetch 入口 + 路由分发
    db.js                D1 访问封装
    storage.js           ★ 存储抽象层（第 5 节）
    pages.js             所有 HTML 页面渲染（搬自 pages.py）
    preflight.js         ★ 上传预检 + 双通道准入（第 6 节）
    handlers/
      upload.js
      download.js
      report.js
      admin.js
      home.js
  ../../../Users/jch/AppData/Local/Temp/ldsg-cloud-verify/   ← 验证脚本放这里（见第 8 节）
```

---

## 4. 数据模型（D1）

**与大本机版 schema 保持一致**，字段名不要改。但要做三处调整，理由写在下面。

### 4.1 建表语句

参考本机版 `D:\AI输出的文件\project_ldsg\db.py` 里的 `SCHEMA`，原样搬到 `schema.sql`，并做以下调整：

1. **`materials` 表增加一个字段**：
   ```sql
   intercept_flag  TEXT     -- 预检命中的规则名，未命中为 NULL
   ```
   理由：记录这份资料在上传时被哪条规则标记过（即使最终被人工放行，也要留痕）。

2. **新增一张表**（这是第 6 节「拦截留痕」用的，**独立于 `audit_log`**）：
   ```sql
   CREATE TABLE IF NOT EXISTS intercept_log (
       id           TEXT PRIMARY KEY,
       action       TEXT NOT NULL,   -- 'rejected'(当场拒绝) / 'flagged'(标记转人审)
       rule         TEXT,            -- 命中的规则名，如 'keyword:xxx' / 'channel:archive'
       filename     TEXT,
       course_code  TEXT,
       byte_size    INTEGER,
       sha256       TEXT,
       ip_hmac      TEXT,
       credential   TEXT,
       created_at   TEXT NOT NULL
   );
   CREATE INDEX IF NOT EXISTS idx_intercept_created ON intercept_log(created_at);
   ```
   **设计意图**：`audit_log` 记的是「审核员的动作」，这张表记的是「系统拦截的动作」。将来要证明「本站对高危内容做过拦截」，靠的是这张表。

3. **D1 建表时注意**：D1 对 `TEXT PRIMARY KEY` 无异议，但**不要用 `AUTOINCREMENT`**（D1 上不适用），主键用应用层生成的随机 ID（沿用本机版做法）。

### 4.2 执行建表

`schema.sql` 里的语句，在部署后用 `wrangler d1 execute` 执行（第 8 节）；在本地开发时用 `wrangler d1 execute --local`。

---

## 5. 存储抽象层（★ 本任务的核心要求之一）

### 5.1 为什么

**数据不能绑死在单一供应商上。** 将来容量不够、或者要加第二个存储源时，业务代码不应该改。这是项目「信息开放可迁移」承诺的技术基础。

### 5.2 接口（`src/storage.js`）

实现一个存储接口，业务代码**只通过它访问文件**，绝不直接调用 R2 API。

```js
// 接口约定（三个核心函数 + 一个 URL 函数）
export class Storage {
  // 写入：返回 {provider, objectKey, size, sha256}
  async put(key, bytes, meta) {}

  // 读取：返回 Uint8Array 或 ReadableStream
  async get(key) {}

  // 列举：返回 [{key, size, uploaded}]
  async list(prefix) {}

  // 下载地址：返回可直接给浏览器的 URL
  async url(key) {}
}
```

### 5.3 第一版实现

```js
// R2 实现
export class R2Storage extends Storage {
  constructor(bucket) { super(); this.bucket = bucket; }
  async put(key, bytes) { await this.bucket.put(key, bytes); ... }
  async get(key) { return await this.bucket.get(key); }
  async url(key) { return `/download/${encodeURIComponent(key)}`; }  // 见 5.4
  ...
}

// 工厂：按配置返回实例
export function createStorage(env) {
  return new R2Storage(env.FILES);
}
```

**注释里写清楚**：将来加第二个源（例如 GitHub Releases、另一个 R2 桶），只需要新增一个类 + 在工厂里按配置选择，**业务代码一行不改**。

### 5.4 下载必须经过 Worker，不给公开直链

项目书第 9 节第 4 条：下载统一走 Worker，不给存储公开直链（防止被当免费图床外链）。

所以 `url()` 返回的是本站路径 `/download/<id>`，由 Worker 去 R2 取再返回（用 `bucket.get()` 拿到的 `body` 流直接作为 `Response` 的 body，**不要 `.arrayBuffer()` 读进内存**）。

### 5.5 `material_sources` 表要用起来

每次 `put()` 成功后，在 `material_sources` 表写一条记录：
`(material_id, provider='r2', object_key, size, sha256, priority=0)`

**即使现在只有一个源也要写**——这样将来加第二个源时，历史数据已经带着「在哪个源」的信息。

---

## 6. 上传预检 + 双通道准入（★ 本任务的核心要求之二）

### 6.1 设计意图

**按内容性质分两条通路，不是「严」「松」的程度问题：**

| | 版权类（教师PPT、旧卷、教材） | 高危类（高法律风险内容） |
|---|---|---|
| 策略 | 先上后诉（默认放行，投诉即下架） | **事前防火墙拦截**（默认拒绝） |
| 位置 | 进正常待审队列 | **在落存储之前拦截**，不进队列、不落库 |

**关键：拦截必须发生在「写存储之前」。** 危险内容不能落 R2、不能进 materials 表、不能被审核员看到。

### 6.2 流程

在 `handle_upload` 里，**读取文件字节之后、调用 `storage.put()` 之前**，插入一个 `preflight()` 环节：

```js
const verdict = await preflight({ filename, mime, size, bytes, title, description, courseCode });
```

`preflight()` 返回三种结果之一：

| verdict | 含义 | 后续动作 |
|---|---|---|
| `{decision: 'allow'}` | 直接放行 | 正常走「待审核」流程，`intercept_flag = NULL` |
| `{decision: 'flag', rule}` | 标记，转强制人审 | 正常入库（pending），但 `intercept_flag = rule`，管理页高亮 |
| `{decision: 'reject', rule}` | 当场拒绝 | **不写存储、不入库**，写 `intercept_log`（action='rejected'），给用户一个拒绝页面 |

### 6.3 判定规则（第一版）

**规则表做成可配置的**，写在 `preflight.js` 顶部的一个常量里，便于以后按咨询结果调整：

```js
// 高危关键词表（第一版留空，等咨询后填入）
export const BLOCKED_KEYWORDS = [
  // TODO: 待填入。填入前，这一项不生效。
];

// 通道分流：这些类型强制人审（不自动放行）
export const FORCE_REVIEW_CHANNELS = {
  '.zip':  '压缩包可藏任意内容',
  '.png':  '图片可藏内容',
  '.jpg':  '图片可藏内容',
  '.jpeg': '图片可藏内容',
  '.txt':  '纯文本',
  '.md':   '纯文本',
};
```

**判定顺序：**

1. **关键词命中** → 检查 `filename`、`title`、`description`、`course_code`
   命中 `BLOCKED_KEYWORDS` → `reject`
2. **通道检查** → 扩展名在 `FORCE_REVIEW_CHANNELS` 里 → `flag`
3. 其余 → `allow`

**注意：关键词表第一版是空的，所以第 1 条不生效——这是故意的。** 机制先搭好、能跑通、能验证；词表内容等咨询后再填。**不要自己去网上找敏感词表填进去**，那是另一个决定。

### 6.4 拦截留痕

`reject` 时写 `intercept_log`（见 4.1），字段：
- `action='rejected'`
- `rule`：例如 `'keyword:xxx'` 或 `'channel:archive'`
- `filename` / `byte_size` / `sha256` / `ip_hmac` / `credential` / `created_at`

`flag` 时也写一条 `intercept_log`（`action='flagged'`），同时在 `materials.intercept_flag` 记下规则名。

### 6.5 管理页要能看到

管理页增加：
- 待审列表里，`intercept_flag` 不为空的资料要有醒目标记（例如红色标签「预检标记：压缩包」）
- 一个「拦截记录」区块，列出最近的 `intercept_log`（action='rejected' 的），只列出时间和规则名，不显示上传者信息

---

## 7. 功能清单（要与本机版一致）

按本机版行为实现，**不要增减功能**：

| 路由 | 方法 | 功能 |
|---|---|---|
| `/` | GET | 首页：已通过资料按时间倒序、每页 20 条、可翻页；搜索；筛选（课程代码/类别/学期） |
| `/upload` | GET | 上传页（表单 + 前端校验） |
| `/upload` | POST | 上传处理（含预检，见第 6 节） |
| `/material/<id>` | GET | 详情页：完整信息 + 下载次数 + 浏览次数 + 举报按钮 |
| `/download/<id>` | GET | 下载（计数 +1，只有已通过资料可下载） |
| `/report` | POST | 举报入库；同一资料累计 3 次未处理自动改为 `removed`（文件不删） |
| `/admin` | GET | 管理页（需 token 登录） |
| `/admin` | POST | token 登录 |
| `/admin/action` | POST | 通过 / 拒绝 / 下架 / 恢复；标记举报已处理 |
| `/about` | GET | 关于页（版权说明 + 投诉通道） |

**硬性规则（照搬本机版）：**
- 单文件上限 50 MB，前端 + 后端都校验
- 类型白名单：`pdf / docx / pptx / xlsx / zip / png / jpg / md / txt / epub`
- sha256 相同 → 提示「已存在」并给原资料链接
- 上传后状态 `pending`
- 系统生成规范文件名，原始名仅管理页可见
- 每个管理动作写 `audit_log`
- 空结果 / 加载中 / 出错都有中文提示，不白屏

**管理令牌**：从环境变量 `ADMIN_TOKEN` 读（本地开发用 `.dev.vars` 文件，**该文件不要提交**）。
**IP 的 HMAC**：用 `IP_HMAC_KEY` 环境变量作为密钥，Web Crypto 的 HMAC-SHA256。**绝不明文存 IP。**

---

## 8. 验证方法（必做）

### 8.1 本地开发环境

```bash
# 在 D:\AI输出的文件\project_ldsg_cloud\ 下
npm install                 # 只装 wrangler
npx wrangler d1 execute ldsg --local --file=schema.sql
npx wrangler dev            # 起本地服务，默认 http://localhost:8787
```

### 8.2 必须跑的验证

**Hermes 侧会独立跑这三项，你也要跑一遍并附真实输出：**

| # | 验证 | 方法 |
|---|---|---|
| 1 | 全流程 | 用 HTTP 请求走：首页 → 上传 → 管理页通过 → 详情 → 下载 → 举报 |
| 2 | 预检拒绝 | 临时往 `BLOCKED_KEYWORDS` 填一个测试词（如 `"TESTBLOCK"`），上传一个标题含该词的文件，确认被拒、且 `intercept_log` 有记录、且 R2 里没有该文件 |
| 3 | 通道标记 | 上传一个 `.zip`，确认状态是 `pending` 且 `intercept_flag` 被设置 |

**第 2 项特别重要**：要证明「命中的文件**既没进 R2、也没进 materials 表**」。这是防火墙位置对不对的判据。

### 8.3 交付要求

1. 改完的代码（全部文件）
2. `SELF_TEST.md`：实际执行过的命令和**真实输出**，包含 8.2 的三项
3. 明确列出你认为**没验证到**的地方

---

## 9. 明确不做（避免跑偏）

- ❌ 不上 React / Vite / Pages / 任何前端构建
- ❌ 不引入 npm 运行时依赖
- ❌ 不做真机测试（需要设备，另议）
- ❌ 不填真实敏感词表（待咨询）
- ❌ 不做公开只读 API（那是 P5）
- ❌ 不做 AI 检索
- ❌ 不修改本机版代码
- ❌ 不注册 Cloudflare 账号、不部署到真云（账号是用户的事；本任务只到「本地 wrangler dev 跑通」）

---

## 10. 卡住了怎么办

**遇到下面任一情况，停下来写清楚，不要自己绕：**

- wrangler 装不上 / 起不来
- D1 本地建表失败
- 某项要求在 Workers 运行时里做不到（例如某个 Web API 不支持）
- 需要引入第三方依赖才能实现某功能

报告格式：

```
## 阻塞
- 卡在哪一步：
- 报错原文：
- 我尝试了什么：
- 我认为的原因：
```

---

## 11. 参考资料

- 本机版参考实现：`D:\AI输出的文件\project_ldsg\`（app.py / pages.py / db.py，**只读参考**）
- 项目进度书：`D:\AI输出的文件\project_ldsg_cloud\项目进度书.md`
- 项目书：`D:\给AI的文件\项目书.pdf`
- wrangler 版本：4.143.0（已装在临时目录，实际以 `project_ldsg_cloud/` 下安装的为准）
