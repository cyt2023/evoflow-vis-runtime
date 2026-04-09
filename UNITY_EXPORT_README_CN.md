# Unity Export README

## Update 2026-04-02

### 这次新增了什么
当前 `EvoFlow + C# OperatorRunner` 后端在保留原有架构不变的前提下，新增了一层 Unity-ready 导出边界。

也就是说，系统内部仍然是：

自然语言任务  
-> LLM 任务解析  
-> EvoFlow 搜索 workflow  
-> C# OperatorRunner 执行  
-> 评分与最佳 workflow 选择

但在最终最佳结果确定之后，会额外产出一个稳定的 Unity-facing JSON。

### 导出 JSON 的作用
这个 JSON 不是给 EvoFlow 内部调试看的，而是给未来 Unity 前端直接消费的。

Unity 后续只需要读取：
- `meta`
- `task`
- `selectedWorkflow`
- `visualization`
- `resultSummary`

它不需要理解：
- 候选种群
- 变异历史
- 原始 prompt
- fitness 计算细节
- 调试日志

### 导出文件在哪里生成
当前由：
[operator_search_main.py](/Users/cyt/Desktop/OperatorsDraft/evoflow/operator_search_main.py)

在最佳 workflow 选出后生成。

默认输出位置是：
[unity_export.json](/Users/cyt/Desktop/OperatorsDraft/exports/unity_export.json)

也可以通过 `--export-json` 指定输出路径。

### 当前 Unity-ready JSON 的核心结构
```json
{
  "meta": {},
  "task": {},
  "selectedWorkflow": {},
  "visualization": {},
  "resultSummary": {}
}
```

其中最关键的是 `visualization`。当前新版导出会把它固定成更明确的 Unity 合同：
- `intent`
- `renderPlan`
- `dataSummary`
- `semanticSummary`

也就是说，Unity 不需要再从后端内部字段里猜“这是什么意思”，而是直接读取：
- 这次任务想展示什么视图
- 是否必须 backend-ready
- 空间/时间过滤是否是硬要求
- 哪些过滤已经被应用
- 哪些点和线需要被渲染
- 当前选中了哪些行和点

### 推荐运行命令
现在也可以直接用仓库根目录的一键脚本：

```bash
/Users/cyt/Desktop/OperatorsDraft/run_evoflow.sh --help
```

例如：

```bash
/Users/cyt/Desktop/OperatorsDraft/run_evoflow.sh \
  --task "Find concentrated morning pickup hotspots in the Hurricane Sandy sample and render them as a backend-ready point visualization." \
  --data-path /Users/cyt/Desktop/OperatorsDraft/demo_data/hurricane_sandy_2012_100k_sample.csv \
  --population 1 \
  --generations 0 \
  --elite-size 1 \
  --export-json /Users/cyt/Desktop/OperatorsDraft/exports/test3.json \
  --task-id test3
```

等价的完整环境变量命令如下：

```bash
PYTHONPATH=/Users/cyt/Desktop/OperatorsDraft/.python_deps \
HOME=/Users/cyt/Desktop/OperatorsDraft \
DOTNET_CLI_HOME=/Users/cyt/Desktop/OperatorsDraft \
PATH=/Users/cyt/Desktop/OperatorsDraft/.dotnet:$PATH \
python3 /Users/cyt/Desktop/OperatorsDraft/evoflow/operator_search_main.py \
  --task "Create a backend-ready STC visualization of morning taxi origin hotspots from the first-week sample after spatial and temporal filtering." \
  --data-path /Users/cyt/Desktop/OperatorsDraft/demo_data/first_week_of_may_2011_10k_sample.csv \
  --population 1 \
  --generations 0 \
  --elite-size 1 \
  --export-json /Users/cyt/Desktop/OperatorsDraft/exports/first_week_unity_export.json \
  --task-id first-week-morning-hotspots
```

### 当前样例导出文件
样例文件已生成在：
[first_week_unity_export.json](/Users/cyt/Desktop/OperatorsDraft/exports/first_week_unity_export.json)

### Unity 以后怎么接
未来 Unity 侧不需要接 EvoFlow 搜索过程本身，只需要：
1. 读取最终导出的 JSON
2. 根据 `visualization.intent.primaryViewType` 和 `visualization.renderPlan.primaryView.type` 选择对应渲染器
3. 根据 `visualization.renderPlan.geometry.points` 和 `visualization.renderPlan.geometry.links` 重建几何对象
4. 根据 `visualization.renderPlan.channels` 恢复位置、颜色、大小编码
5. 根据 `visualization.renderPlan.filtersApplied` 和 `visualization.renderPlan.selection` 恢复这次任务的筛选语义与高亮结果

这样 Unity 可以作为一个纯前端消费者，而 EvoFlow 继续保持后端 planner + executor 的角色。

## Update 2026-04-03

### 本次新增
在原有 `task parsing` 前面，新增了一层 `CSV schema inference`。

新的入口顺序变成：

CSV  
-> 数据结构抽样  
-> 规则 + LLM 推断数据 schema  
-> task parsing  
-> EvoFlow workflow search  
-> C# OperatorRunner execution  
-> Unity-ready JSON export

### 这一层解决了什么问题
之前系统虽然已经能跑通，但仍然依赖我们在代码里提前知道：
- 哪列是 id
- 哪列是 time
- 哪列是 origin / destination
- 哪列适合做 color / size / filter

现在这一层会先自己读取 CSV 的 header 和 sample rows，再推断：
- 数据更像 `OD` 还是 `Point`
- 候选 id 列
- 候选时间列
- 候选坐标列
- 候选数值编码列

如果 LLM 可用，就会在 heuristic 结果上再做一轮语义修正；如果 LLM 不可用，就回退到规则推断结果。

### 当前意义
这一步让后端更接近“面向任意新数据”的最终目标，而不是只能处理事先手工写好字段名的 demo CSV。

## Update 2026-04-09

### 本次新增
导出 JSON 合同升级到 `schemaVersion = 2.0.0`，目标是让 Unity 不需要依赖 LLM，也不需要理解后端调试语义，只要按固定字段就能执行。

### 为什么要升级
旧版导出虽然已经包含了 `primaryView / points / links / selectionState / queryContext`，但这些字段更像“后端原始执行载荷”，Unity 仍然需要自己推断：
- 这次任务真正的显示意图是什么
- 哪些过滤是必须的
- 哪些过滤已经生效
- 什么字段应该被拿来做位置/颜色/大小编码

新版导出把这些含义直接写成固定合同。

### 新版 `visualization` 结构
```json
{
  "intent": {
    "primaryViewType": "Point",
    "targetRole": "Origin",
    "backendReadyRequired": true,
    "spatialFilterRequired": true,
    "temporalFilterRequired": true,
    "hotspotFocus": true
  },
  "renderPlan": {
    "status": "ready",
    "primaryView": {},
    "coordinatedViews": [],
    "channels": {},
    "filtersApplied": {},
    "selection": {},
    "geometry": {
      "points": [],
      "links": []
    }
  },
  "dataSummary": {},
  "semanticSummary": {}
}
```

### 这意味着什么
未来 Unity 侧可以直接按如下方式工作：
1. 先看 `intent`，知道任务想展示什么
2. 再看 `renderPlan.primaryView`，知道最终实际该渲染什么
3. 用 `channels` 决定位置/颜色/大小编码
4. 用 `filtersApplied` 恢复空间、时间和组合过滤状态
5. 用 `selection` 做最终高亮
6. 用 `geometry.points` 和 `geometry.links` 真正生成图元

这样 Unity 读 JSON 的过程不需要“猜意思”，而是按明确字段执行。
