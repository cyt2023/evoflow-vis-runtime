# EvoFlow + Operator Workflow Update Log

## Update 2026-04-01

### 标题

EvoFlow + C# Operator Workflow 端到端原型打通

### 本次更新概述

这次更新把仓库从“算子定义 + 独立的 EvoFlow 草稿”推进到了一个**可运行的端到端原型**，核心链路如下：

`自然语言任务 -> LLM 任务解析 -> EvoFlow 搜索算子 workflow -> C# operator runner 执行 -> LLM 结果评估 -> 输出最佳 workflow`

也就是说，当前版本已经不再只是：
- 单独展示 C# 算子
- 单独跑一个 LLM workflow 演化 toy example

而是把两者接起来，做成了一个真正可以从自然语言任务出发、自动搜索并执行算子流程的原型系统。

### 本次新增的关键能力

### 1. 统一的 C# operator runner

新增了一个 .NET 控制台入口：

- `OperatorRunner/Program.cs`
- `OperatorRunner/OperatorRunner.csproj`

它可以：
- 接收 JSON request
- 按给定 workflow 顺序执行现有 C# 算子
- 返回执行结果、自评结果和诊断信息

目前已支持的核心算子类型包括：
- Data operators
- View operators
- Query operators
- Filter operators
- Backend operators

### 2. EvoFlow 从算子池中搜索 workflow

新增了一个主入口：

- `evoflow/operator_search_main.py`

这个脚本已经实现：
- 从**全算子池**中随机生成候选算子集合
- 修复为可执行 workflow
- 对 workflow 做交叉、变异、保留
- 调用 C# runner 执行每个候选
- 根据执行结果和 LLM 评分计算 fitness

这意味着 EvoFlow 现在搜索的是**你的 C# operator workflow**，而不是只搜索：
- `CoT-small`
- `Debate`
- `SelfRefine`

这一步是这次更新最关键的变化。

### 3. 自然语言任务输入

当前可以直接在终端里输入自然语言任务，程序会先尝试让 LLM 解析任务，再转换成结构化 task spec。

目前链路是：

1. 用户输入自然语言任务
2. Qwen 对任务做结构化解析
3. 若解析失败或超时，则 fallback 到 heuristic task spec
4. 再由 EvoFlow 继续搜索 workflow

这意味着系统已经支持“从文本任务出发”而不是必须手工写死任务参数。

### 4. LLM 在系统中的两个角色

当前版本里，LLM 不是直接替 EvoFlow 选算子，而是承担两个角色：

### A. 任务理解

把自然语言任务解析成 task spec，例如：
- `requiredViewType`
- `atomicMode`
- `requireBackendBuild`
- `spatialRegion`
- `timeWindow`

### B. workflow 结果语义评估

在 C# runner 执行完 workflow 后，Qwen 会根据：
- 任务描述
- workflow 内容
- 执行结果

给出一个语义评分和简短理由。

最终 fitness 由以下几部分共同组成：
- execution score
- LLM score
- cost penalty
- exact match / view bonus / backend bonus

### 5. 终端可见的完整运行过程

当前终端日志已增强，运行时会输出每一步，包括：

- `Step 1`: 原始任务文本
- `Step 2`: LLM 任务解析 prompt
- `Step 3`: 解析后的 task spec
- `Step 4`: 每个候选 workflow proposal
- `Step 5`: C# runner request / response
- `Step 6`: LLM workflow evaluation prompt
- `Step 7`: LLM workflow evaluation raw response
- `Step 8`: 每代最优个体
- `Final`: 最佳 workflow 与执行结果

因此现在可以直接把终端日志复制出来做分析。

### 本次已完成的本地测试

### 测试任务

终端输入任务：

`给我筛选早高峰起点热点并做点图`

### 当前系统实际运行效果

在一次真实运行中，系统完成了以下步骤：
- 成功读取自然语言任务
- 成功调用 Qwen 做任务解析
- 成功 fallback 或使用解析结果构造 task spec
- 成功让 EvoFlow 从算子池中生成多个候选 workflow
- 成功调用 C# operator runner 执行 workflow
- 成功调用 Qwen 对 workflow 结果做评分
- 成功输出最终最佳 workflow

### 一个实际跑出的最终最佳 workflow

例如一次运行中得到的最佳 workflow 为：

1. `ReadDataOperator`
2. `NormalizeAttributesOperator`
3. `MapToVisualSpaceOperator`
4. `BuildSTCViewOperator`
5. `CreateAtomicQueryOperator`
6. `CreateDirectionalQueryOperator`
7. `RecurrentQueryComposeOperator`
8. `ApplySpatialFilterOperator`
9. `UpdateViewEncodingOperator`
10. `AdaptedIATKViewBuilderOperator`

### 该次运行的结果

- `ViewType: STC`
- `SelectedRowIds: ['T1', 'T5', 'T6']`
- `SelectedPointCount: 3`
- `BackendBuilt: True`
- `ExecutionScore: 0.52666664`
- `LLMScore: 0.5`
- `Fitness: 0.5373`

这说明：
- 系统已经真正可以运行
- 但当前 fitness 和任务解析还需要继续调优
- 尤其是在“点图任务”中，系统仍可能偏向 `STC` 而不是 `Point`

### 本次测试中发现的问题

这次测试中也暴露了几个重要问题：

### 1. 任务解析延迟较高

即使使用了较轻的模型，任务解析有时仍较慢，因此已加入：
- 超时提示
- fallback 机制

### 2. workflow 结果仍可能与任务目标不一致

例如“做点图”任务下，系统有时仍会选出：
- `BuildSTCViewOperator`

说明当前：
- task spec 约束还不够强
- fitness 对视图类型错误的惩罚还不够大

### 3. filtering 与 query 组合仍会出现冗余

例如某些任务中会选出：
- `CreateDirectionalQueryOperator`
- `RecurrentQueryComposeOperator`
- `MergeQueriesOperator`

即使这些算子对当前任务帮助不大。

### 当前版本的意义

这次更新的价值不是“已经收敛到最优 workflow”，而是：

**已经把 EvoFlow、LLM、C# operator execution 三者打通，做成了一个真实可运行的端到端原型。**

这是一个关键里程碑，因为它证明了：

- EvoFlow 可以不再只优化抽象 LLM strategy
- 它可以开始优化真实的 operator workflow
- 自然语言任务可以被引入这个闭环
- workflow 的评估不再只是 fake score，而是基于真实执行结果和 LLM 语义判断

### 下一步可继续优化的方向

后续如果继续推进，最值得做的方向是：

1. 强化 task spec 对视图类型的约束
2. 提高 fitness 对错误 view type 的惩罚
3. 加强结果集匹配（selectedRowIds）的权重
4. 减少无效复杂 query operator 的奖励
5. 优化 LLM 请求耗时和缓存机制
6. 扩展到更多真实数据集，而不只停留在 taxi OD demo data

## Update 2026-04-03

### 标题

Qwen 连通性确认、CSV 泛化测试、终端摘要输出与卡顿缓解

### 本次更新概述

这次更新没有改动系统的大框架，而是围绕“让现有原型更稳定、更容易测试”做了三类增强：

1. 确认本机环境下 Qwen 是真的可以被调用的  
2. 用新增的 `hurricane_sandy_2012_100k_sample.csv` 做泛化测试，验证 CSV schema inference 能自动识别新数据结构  
3. 收紧终端日志，避免运行时输出过多细节导致看起来像“跑一半不动”

### 本次做了什么

### 1. 确认 Qwen 在用户本机可真实调用

之前在受限执行环境里，日志中多次出现：
- `Failed to resolve 'dashscope-intl.aliyuncs.com'`

这会让人误以为系统没有真正接上 Qwen。后来通过用户本机终端验证：

- `nslookup dashscope-intl.aliyuncs.com` 成功解析
- 最小 `run_qwen_llm()` 测试成功返回

因此可以确认：
- 代码侧的 Qwen 接入没有问题
- 用户本机网络环境下，Qwen 是真的可以参与 task parsing / schema inference / workflow evaluation 的
- 之前失败主要是受限沙箱环境的 DNS/外网限制，不代表项目本身不能调用 AI

### 2. 用 Hurricane Sandy 新 CSV 做自动结构识别测试

对新增文件：

- `demo_data/hurricane_sandy_2012_100k_sample.csv`

系统自动识别出了：
- `tripIdColumn = column_0`
- 起点坐标：`pickup_longitude / pickup_latitude`
- 终点坐标：`dropoff_longitude / dropoff_latitude`
- 时间列：`pickup_datetime`
- `colorColumn = fare_amount`
- `sizeColumn = passenger_count`

这说明当前 schema inference 已经不再只依赖手工写死的 CSV 字段名，而是可以先看 header 和 sample rows，再推断结构。

### 3. 调整终端日志，只显示关键信息

之前大数据集测试时，终端会打印：
- 巨量 `selectedRowIds`
- 整块 `Runner response`
- 很长的 LLM raw response

这会带来两个问题：
- 终端看起来像“卡住了”
- 关键信息被海量细节淹没

这次在：

- `evoflow/operator_search_main.py`

里做了日志摘要化处理：
- 大列表只显示 `count + sample`
- 长文本只显示截断后的 preview
- `SelectedRowIds` 不再整串打印
- `Runner response` 和 `LLM raw response` 只保留摘要

这样最后终端会更清楚地展示：
- 最佳 workflow
- 视图类型
- 选中数量
- backend 是否构建
- fitness / execution / llm score

### 4. 给 workflow 的 LLM 评估增加硬超时

之前即使日志里出现：
- `[Qwen] Completed successfully ...`

终端后续仍可能因为返回文本过长或后处理较重而显得卡顿。

这次新增了：
- workflow 级 LLM evaluation timeout
- 更稳的 fallback 行为

即使评估阶段的 Qwen 返回较慢或异常，也会自动退回：
- `LLM evaluation timed out.`
- 或 `LLM evaluation unavailable.`

从而保证整条主链不会停在中途。

### 为什么现在看起来可以更顺畅地调用 AI

原因分成两层：

### A. 连通性问题被澄清了

现在已经确认：
- 用户本机可以成功调用 Qwen
- 之前“不行”不是代码没接上，而是受限环境网络问题

所以现在在你自己的 Mac 终端里跑时，AI 会真实参与。

### B. 就算 AI 慢或失败，流程也更稳

这次增加的：
- 超时
- fallback
- 摘要日志

让系统从“有时看起来卡死”变成了：
- 要么正常拿到 AI 返回
- 要么明确提示 fallback
- 最终仍能输出结果摘要

所以你现在看到的是一种更顺畅的体验：
不是 AI 一定更快了，而是系统对 AI 请求的处理更稳、更可见了。

### 本次测试结果摘要

在任务：

`Create a backend-ready STC visualization of Hurricane Sandy taxi origin hotspots with spatial and temporal filtering.`

上，系统最终输出了：

- `ViewType: STC`
- `SelectedRowIds: count=68443 sample=[...]`
- `SelectedPointCount: 68443`
- `BackendBuilt: False`
- `Fitness: 0.3685`
- `ExecutionScore: 0.29`
- `LLMScore: 0.5`

这说明：
- 系统已经可以稳定跑完整条主链
- 但当前最优 workflow 质量还一般
- 主要瓶颈已经从“能不能跑”转向“结果好不好”

### 当前阶段的意义

这一轮之后，可以更明确地说：

- CSV 自动结构识别已经基本接通
- Qwen 在用户本机环境中可以真实调用
- 整个 EvoFlow + OperatorRunner + LLM 主链已可持续测试
- 终端输出已经适合日常实验，不再被大块 debug 信息淹没

下一步更值得继续优化的是：
- fitness 设计
- backend-ready 约束
- temporal filter 是否真正生效

### 同日追加：任务意图显式进入 fitness

在后续继续优化中，又补了一轮更偏“算法效果”的改进，核心是把任务里的真实要求显式写进评分逻辑，而不是继续只看：
- execution score
- llm score
- 简单 bonus

新增了 `taskHints`，会从自然语言任务里提取：
- `requireBackendBuild`
- `requireTemporalFilter`
- `requireSpatialFilter`
- `hotspotFocus`

这些信号现在会进入：
- `task spec`
- `runner request`
- `fitness calculation`

评分时会额外检查：
- view type 是否真的匹配
- backend 是否真的构建完成
- temporal filter 是否真的产生了结果
- spatial filter 是否真的生效
- hotspot 任务下结果是否选得过宽

例如在 Hurricane Sandy 的测试中，同一条 workflow 虽然还能运行，但由于：
- `BackendBuilt = False`
- `TemporalSelectedCount = 0`
- `selectionRatio = 0.986`

新的 fitness 会把它从之前相对偏高的分数，压到更低的区间。  
这意味着系统开始更接近“判断任务是否真正完成”，而不是只判断“workflow 是否跑通”。

## Update 2026-04-07

### 标题

弱监督质量评分接入，解决新数据集 `Precision / Recall / F1` 长期为 0 的问题

### 本次更新概述

这次优化的重点不再是“让系统跑起来”，而是让它在没有人工标准答案的新数据集上，也能给出更合理的结果质量分。

之前在 `hurricane_sandy_2012_100k_sample.csv` 这类新数据上，虽然 workflow 已经越来越合理，但：
- `Precision = 0`
- `Recall = 0`
- `F1 = 0`

原因不是 workflow 一定完全没效果，而是原来的 C# 自评逻辑只要 `expectedRowIds` 为空，就会天然按“空 ground truth”计算，所以内容层评分永远拿不到分。

### 这次做了什么

### 1. C# runner 自评改成双模式

修改文件：
- `OperatorRunner/Program.cs`

现在自评逻辑变成：

#### A. 有明确 `expectedRowIds`
继续沿用原来的目标集匹配评分：
- precision
- recall
- f1

#### B. 没有明确 `expectedRowIds`
切换到 heuristic selection-quality evaluation，根据以下行为信号估分：
- 最终是否真的选中结果
- 结果集是否过宽或过散
- spatial filter 是否真正起作用
- temporal filter 是否真正起作用
- final mask 是否保留下有效结果

也就是说，系统现在已经具备了：

**没有人工标注答案时，也能做“弱监督质量评估”的能力。**

### 2. 把 task hints 传进 C# runner 自评

在 Python 侧我们已经有：
- `requireBackendBuild`
- `requireTemporalFilter`
- `requireSpatialFilter`
- `hotspotFocus`

这次把这些 `taskHints` 正式传进了 C# runner 的 `RunnerRequest`，并让弱监督评分根据任务意图调整：
- hotspot 任务下，对“选中集过宽”更敏感
- temporal/spatial 明确要求时，对对应 filter 生效情况加更高权重

这意味着现在的弱监督评分不是一个通用固定规则，而是：

**会根据当前任务语义来动态判断 workflow 质量。**

### 本次测试结果

在任务：

`Please build a backend-ready STC view for Hurricane Sandy taxi origins during the morning peak after spatial and temporal filtering.`

上的结果，从之前的：
- `Precision = 0`
- `Recall = 0`
- `F1 = 0`

变成了：
- `Precision = 0.35`
- `Recall = 0.35`
- `F1 = 0.35`
- `ExecutionScore = 0.6025`
- `Fitness = 0.7216`

同时日志中会明确标出：

- `No expected row ids were provided; heuristic selection-quality evaluation was used.`

### 当前意义

这一轮之后，系统在“没有人工 ground truth 的新数据集”上，已经不再是：
- 内容层分数恒为 0

而是进入了：
- 可以用弱监督方式近似判断结果质量
- 可以把 task intent 一起纳入质量评分

这对于后续做跨数据集泛化非常重要，因为现实里多数新 CSV 一开始都不会有人手工标注 `expectedRowIds`。

## Update 2026-04-09

### 标题

LLM 主评估稳定化、弱监督结果评分落地、Unity 导出合同升级

### 本次更新概述

这次更新的重点不再是“系统能不能跑通”，而是继续把系统往更可靠评估和更明确前后端边界上推进。

本轮主要完成了三件事：

1. 让 workflow 结果评估尽量由 LLM 主导，而不是长期停留在 fallback
2. 在没有人工 `expectedRowIds` 的新数据集上，引入可用的弱监督质量评分
3. 把最终导出的 Unity JSON 收敛成更明确、更固定的前端合同

### 本次做了什么

### 1. LLM workflow evaluation 改成主评估路径

之前 workflow 评估这一步经常出现：
- `LLM evaluation timed out`
- `LLM evaluation unavailable`

虽然系统还能依靠 C# runner 自评继续跑完，但这样 `LLMScore` 实际上没有真正发挥主评估作用。

这次做了两类调整：
- 把 workflow evaluation 从较重模型切到更轻的 `small / qwen-turbo`
- 给 workflow evaluation 增加多次自动重试，而不是一次超时就直接 fallback

同时，fitness 权重也调整为更偏向 LLM：
- `0.4 * execution score`
- `0.6 * llm score`

这意味着当前版本里：
- LLM 是 workflow 语义评估的主路径
- C# runner 自评更多作为辅助信号和 fallback

### 2. 新数据集不再因为没有 ground truth 而内容分全 0

之前在 `hurricane_sandy_2012_100k_sample.csv` 这种没有人工标注目标行 id 的数据上，系统虽然能跑通，但：
- `Precision = 0`
- `Recall = 0`
- `F1 = 0`

这并不表示 workflow 一定完全错误，而是因为旧逻辑默认把“缺少 expected row ids”当成空 ground truth。

这次在 C# runner 侧正式加入了双模式结果评分：

1. 有 `expectedRowIds` 时
   按真实目标集计算 `precision / recall / f1`

2. 没有 `expectedRowIds` 时
   改为 heuristic selection-quality evaluation，根据这些特征估计内容质量：
   - 是否真的筛到了结果
   - 结果是否过宽
   - spatial filter 是否真生效
   - temporal filter 是否真生效
   - final mask 是否留下有效结果

因此现在新数据集已经不再是“没有人工答案就内容评分全废”，而是具备了弱监督质量判断能力。

### 3. 任务意图开始更直接影响 workflow 选择

本轮继续把自然语言任务里更关键的意图显式传入系统，包括：
- `backend-ready`
- `temporal filtering`
- `spatial filtering`
- `hotspot focus`

这些 `taskHints` 不只用于 Python 侧 fitness，也会传给 C# runner，用于弱监督自评。

同时 workflow repair / candidate 生成也会更积极地保留：
- `EncodeTimeOperator`
- `ApplyTemporalFilterOperator`
- `CombineFiltersOperator`
- `AdaptedIATKViewBuilderOperator`

因此对于像：

`Find concentrated morning pickup hotspots in the Hurricane Sandy sample and render them as a backend-ready point visualization.`

这样的任务，最佳 workflow 现在已经更稳定地包含：
- 时间编码
- 空间过滤
- 时间过滤
- 组合过滤
- backend build

### 4. Unity 导出合同升级到更明确的固定结构

之前导出的 Unity JSON 虽然已经可用，但 `visualization` 部分更接近“后端原始执行载荷”，Unity 仍然需要自己推断：
- 任务真正想展示什么
- 哪些过滤是硬要求
- 哪些过滤已经生效
- 哪些字段应该作为位置/颜色/大小编码

这次把导出合同升级到：
- `schemaVersion = 2.0.0`

并把 `visualization` 固定为：
- `intent`
- `renderPlan`
- `dataSummary`
- `semanticSummary`

其中 `renderPlan` 进一步细分为：
- `primaryView`
- `coordinatedViews`
- `channels`
- `filtersApplied`
- `selection`
- `geometry`

这样未来 Unity 不需要借助 LLM，也不需要再从后端内部字段里猜意思，而是可以按明确合同直接执行。

### 本次测试结果

### 测试数据

- `demo_data/hurricane_sandy_2012_100k_sample.csv`

### 测试任务

`Find concentrated morning pickup hotspots in the Hurricane Sandy sample and render them as a backend-ready point visualization.`

### 本次实际跑出的最终结果

最终最佳 workflow 为：

1. `ReadDataOperator`
2. `FilterRowsOperator`
3. `NormalizeAttributesOperator`
4. `EncodeTimeOperator`
5. `MapToVisualSpaceOperator`
6. `BuildPointViewOperator`
7. `CreateAtomicQueryOperator`
8. `CreateDirectionalQueryOperator`
9. `RecurrentQueryComposeOperator`
10. `MergeQueriesOperator`
11. `ApplySpatialFilterOperator`
12. `ApplyTemporalFilterOperator`
13. `CombineFiltersOperator`
14. `UpdateViewEncodingOperator`
15. `AdaptedIATKViewBuilderOperator`

执行结果为：
- `ViewType: Point`
- `SelectedRowIds count: 1322`
- `SelectedPointCount: 1322`
- `BackendBuilt: True`
- `SpatialSelectedCount: 28908`
- `TemporalSelectedCount: 2710`
- `FinalSelectedCount: 2646`

评分结果为：
- `ExecutionScore: 0.6025`
- `LLMScore: 0.6`
- `Fitness: 0.756`
- `Precision: 0.35`
- `Recall: 0.35`
- `F1: 0.35`

一次成功的 LLM 语义评价理由为：

`The workflow completed necessary steps including spatial/temporal filtering and backend build, but metrics suggest limited precision in hotspot identification.`

这说明当前系统已经不是只会“跑通”，而是开始具备：
- 较稳定的任务理解
- 较稳定的 Point/STC 视图匹配
- 真正生效的 temporal filtering
- backend-ready 结果构建
- 弱监督条件下仍可用的内容质量评分

### 当前版本的意义

这轮更新把系统从：

**“能跑的原型”**

进一步推进到了：

**“评估更合理、结果更稳定、前后端边界更明确的可持续迭代版本”**

现在系统已经可以：
- 对不同 CSV 自动识别结构
- 用自然语言任务驱动 workflow 搜索
- 用 LLM 作为更主要的语义评估者
- 在没有人工真值时仍给出可用的弱监督内容评分
- 产出更适合未来 Unity 直接消费的固定 JSON 合同

### 补充完成内容

### 5. 增加一键启动脚本，降低环境变量错误风险

为了避免每次手动输入：
- `PYTHONPATH`
- `HOME`
- `DOTNET_CLI_HOME`
- `PATH`

导致 `.dotnet build` 或 Python 依赖环境出错，新增了仓库根目录脚本：

- `run_evoflow.sh`

现在可以直接通过：

```bash
./run_evoflow.sh ...
```

来运行整条主链，减少环境配置错误带来的假性失败。

### 6. 为 Unity 对接同时准备 full JSON 和 schema sample JSON

考虑到 Unity 侧一开始做格式适配时，不一定适合直接面对超大的 full render JSON，这次同时准备了两类导出：

1. 真实完整导出：
   - `exports/test3.json`

2. 轻量 schema 示例：
   - `exports/test3_schema_sample.json`

其中：
- `test3.json` 用于 Unity 最终真实接入
- `test3_schema_sample.json` 用于 Unity AI / 开发侧先做字段结构适配

这样可以避免一开始因为 full geometry 过大而影响对接效率，同时又保证最终仍然以真实完整 JSON 为准，不会偏离后端实际输出结构。

### 下一步建议

后续最值得继续做的方向是：

1. 继续提高 hotspot 结果的集中度，进一步提升 `precision / recall / f1`
2. 继续降低 Qwen 慢请求拖尾的影响，提高 LLM evaluation 成功率
3. 用更多不同结构的新 CSV 压测 schema inference 与任务泛化能力
4. 继续打磨 Unity 合同，让前端几乎不需要任何语义推断
