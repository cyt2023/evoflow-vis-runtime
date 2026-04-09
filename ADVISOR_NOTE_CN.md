# ImmersiveTaxiVis Visualization Core Operator 化说明

## 1. 文档目的

本文说明当前这个 C# operator package 的设计目标、与原始 Unity 项目 `ImmersiveTaxiVis` 的对应关系，以及当前版本的完成程度。

这份 package 的目标不是复刻完整 Unity 原型，也不是覆盖 VR、MRTK、Bing Maps 或场景交互外壳；它的目标是把 **ImmersiveTaxiVis 的 visualization core** 重组为一套更明确、可解释的 operator-based decomposition。

换句话说，这份工作关注的是：

- OD 数据如何进入系统
- 如何被映射为 STC / 点视图 / 链接视图 / 2D 投影视图
- query 如何被表示为显式对象
- filter 如何作用于这些 query
- 结果如何传播到渲染后端

而不是：

- VR 手势与沉浸式交互细节
- MRTK 控件和场景 UI
- Bing Maps 地图服务
- 原型系统中的环境与外壳逻辑


## 2. 对原始项目的理解

在阅读原始 `ImmersiveTaxiVis` 项目后，我对其 visualization core 的理解是：

### 2.1 它不是一个普通散点图系统

原项目不是把 taxi 数据简单映射为一个通用 scatterplot，而是围绕 **bipartite OD trip data** 构建的。

对每一条 trip 记录，系统概念上同时维护：

- 一个 origin / pickup 点
- 一个 destination / dropoff 点
- 一条 origin-destination link

因此，原始项目的核心不是单点集合，而是 **双端点 + 连接关系**。

### 2.2 它构建的是可查询的 Space-Time Cube

原项目中的 STC 不是普通 3D 点云，而是一个具有明确时间语义的空间-时间结构：

- 空间位置映射到平面坐标
- 时间映射到 STC 高度
- query 可以作为时空体积作用在该结构上

原始系统还显式维护了：

- 时间范围
- 时间方向
- 空间范围
- 时间到高度、以及高度到时间的映射关系

因此，时间在原项目里不是附加属性，而是 STC 的核心轴。

### 2.3 它是多视图协调系统

对 taxi-like OD 数据，原始项目的核心可视化不是单一 view，而是多视图组合：

- pickup point view
- dropoff point view
- linking view
- spatial 2D projection views
- temporal 2D projection views

这些 view 不是彼此独立，而是由统一的 query/filter 结果协调更新。

### 2.4 query 在原项目里是显式对象，而不是普通筛选条件

原项目中存在多种 query 类型，例如：

- atomic query
- directional query
- merged query
- recurrent query

这些 query 之间不仅有类型区别，而且具有不同的语义结构和组合方式。

例如：

- atomic query 可以针对 origin、destination 或 either
- directional query 表达 OD 方向关系
- recurrent query 表达时间模式上的重复切片与组合

所以，query 在原项目中本身就是 visualization core 的重要结构，而不只是“筛选谓词”。

### 2.5 原项目强调 filter 结果的高效传播，而不是每次重建 mesh

原始 `ImmersiveTaxiVis` 通过 Adapted IATK 和 compute-shader-based logic，使 query / brushing 的结果能够高效传播到多个视图，而不是每次重建新的 mesh。

这意味着原项目的重要抽象链条是：

`raw OD table -> visual mapping -> view structures -> query objects -> filter execution -> backend update`

而不是：

`raw data -> filter rows -> redraw everything`


## 3. 当前 operator package 的设计目标

基于上述理解，这个 operator package 的设计目标是：

### 3.1 将 visualization core 拆成显式 operator categories

当前 package 将系统分成以下几类 operator：

- Data operators
- View construction operators
- Query operators
- Filter execution operators
- Backend operators

这样做的目的是把原始项目中混合在 Unity scene / manager / component 中的可视化核心职责，重新组织结构。

### 3.2 保留原项目的核心概念，而不是只保留表面名称

本次拆分努力保留的不是文件名层面的相似，而是以下核心概念：

- OD 双端点语义
- STC 的显式时间语义
- 多视图分离
- query 作为对象
- filter 与 query 分离
- backend 作为单独层

### 3.3 接受的简化

当前 package 不试图在这一阶段实现：

- Unity runtime 场景行为
- MRTK 交互逻辑
- Bing Maps 依赖
- 真正的 compute shader / texture backend




## 4. 当前版本的结构

### 4.1 Core

`Core/` 中定义了 package 的共享结构，包括：

- `TabularData`
- `VisualMapping`
- `VisualPointData`
- `QueryDefinition`
- `FilterMask`
- `ViewRepresentation`

这一层负责表达：

- 原始表格数据
- 可视映射规则
- OD 点与 link
- query 对象
- 过滤结果
- view 抽象

### 4.2 Data operators

`Data/` 中包括：

- `ReadDataOperator`
- `FilterRowsOperator`
- `NormalizeAttributesOperator`
- `EncodeTimeOperator`
- `MapToVisualSpaceOperator`

其中最重要的是：

- `EncodeTimeOperator`
- `MapToVisualSpaceOperator`

因为它们把输入数据推进到 STC / OD 可视化语义。

### 4.3 View operators

`View/` 中包括：

- `BuildPointViewOperator`
- `BuildSTCViewOperator`
- `Build2DProjectionViewOperator`
- `BuildLinkViewOperator`

这层的目标是把不同 view 的构建职责显式化，而不是让“一个大 manager”同时承担所有 view 组织逻辑。

需要说明的是：

- `BuildPointViewOperator` 与 `BuildLinkViewOperator` 更接近基础视图构造算子
- `BuildSTCViewOperator` 更接近组合型算子，它在 OD 语义存在时会组织出一个协调的 STC view bundle

因此，这里存在的是“组合关系”，不是无意义的重复定义。

### 4.4 Query operators

`Query/` 中包括：

- `CreateAtomicQueryOperator`
- `CreateDirectionalQueryOperator`
- `MergeQueriesOperator`
- `RecurrentQueryComposeOperator`

这层的目标是表达：

- query 是对象
- query 类型不同
- query 可以组合

### 4.5 Filter operators

`Filter/` 中包括：

- `ApplySpatialFilterOperator`
- `ApplyTemporalFilterOperator`
- `CombineFiltersOperator`
- `UpdateViewEncodingOperator`

这里明确将：

- query definition
- filter execution
- view update

拆开处理。

### 4.6 Backend

`Backend/` 中包括：

- `IAdaptedIATKAdapter`
- `AdaptedIATKViewOperator`
- `AdaptedIATKViewBuilderOperator`

这层的目标是保留原项目中“渲染后端单独存在”的思想，使 operator package 不把渲染实现细节混进 query 或 data 层中。

### 4.7 算子功能与约束

下面对当前主要算子的职责、边界与约束作统一说明。

#### Core structures

- `TabularData`
  作用：承载原始表格数据、列集合与 metadata。
  约束：当前假设输入能够被整理为行列式 tabular structure，不处理复杂层级数据格式。

- `VisualMapping`
  作用：定义从表格列到可视通道的映射规则，包括 OD 双端点与 STC 时间字段。
  约束：当使用 OD 语义时，要求 origin/destination 相关列成组提供；否则只能退化为 generic point mapping。

- `VisualPointData`
  作用：表达映射后的可视数据，包括 points、links、time range 与 OD 语义标记。
  约束：当前仍以单个内存结构承载 origin/destination/link，并未实现原项目中按 pickup/dropoff/linking 分离的 GPU 纹理表示。

- `QueryDefinition`
  作用：表达 atomic、directional、merged、recurrent 等 query 结构。
  约束：当前主要是结构性表达与参数表达，不等同于原项目中完整的 Unity runtime query object 生命周期。

- `FilterMask`
  作用：表达 filter 执行结果。
  约束：当前是逻辑掩码模型，不是原项目中的 brushed/filter texture 模型。

- `ViewRepresentation`
  作用：表达 view 抽象、编码状态与协调子视图。
  约束：当前是抽象层 representation，不是完整的 Adapted IATK runtime view。

#### Data operators

- `ReadDataOperator`
  作用：读取原始表格数据。
  约束：当前采用简单 CSV 读取逻辑，不覆盖更复杂的数据清洗与解析问题。

- `FilterRowsOperator`
  作用：在 tabular 层进行通用行过滤。
  约束：它是通用预处理算子，不应与 query/filter execution 层混淆。

- `NormalizeAttributesOperator`
  作用：对数值列做归一化。
  约束：当前按列独立归一化，不表达原项目中更细的语义型映射策略。

- `EncodeTimeOperator`
  作用：将时间字段编码为 STC 可用的数值，并保留时间范围 metadata。
  约束：当前保留的是基础时间语义，还没有实现原项目中的时间方向、时间到高度、以及高度到时间的完整映射逻辑。

- `MapToVisualSpaceOperator`
  作用：将 OD 表格映射为 origin points、destination points 与 links。
  约束：这是当前最关键的数据语义算子；它已体现 OD 语义，但尚未表达原项目 runtime 中更复杂的地图、墙面和坐标系统更新机制。

#### View operators

- `BuildPointViewOperator`
  作用：构建单一角色的点视图。
  类型：primitive operator。
  约束：适合表达 pickup 或 dropoff 的单视图，不负责多视图协调。

- `BuildLinkViewOperator`
  作用：构建 OD 链接视图。
  类型：primitive operator。
  约束：当前仅表达 link view 结构，不包含原项目中 linking material 与 shader 行为。

- `Build2DProjectionViewOperator`
  作用：构建 2D projection view。
  类型：primitive operator。
  约束：当前通过 `ProjectionKind` 与 `Plane` 区分投影类型，但尚未完整表达原项目中 spatial/time projections 的全部协调关系。

- `BuildSTCViewOperator`
  作用：组装 STC 核心 view bundle。
  类型：composite operator。
  约束：它本身并不替代 primitive point/link operators，而是在 OD 语义存在时组合出协调的 STC bundle；当前表达的是结构组合，不是 Unity scene 中的完整交互性 STC object。

#### Query operators

- `CreateAtomicQueryOperator`
  作用：构建 atomic query，并显式表达 `Origin / Destination / Either`。
  约束：当前支持区域与时间窗口定义，但还没有完整复刻原项目中 prism object 与 wall projection 的运行时关系。

- `CreateDirectionalQueryOperator`
  作用：将 origin query 与 destination query 组合成 directional query。
  类型：composite operator。
  约束：当前保留了定向 OD 语义，但仍以结构组合为主，尚未发展到原项目 `QueryManager` 中完整的执行级联逻辑。

- `MergeQueriesOperator`
  作用：将多个 query 合并为 merged query。
  类型：composite operator。
  约束：当前表达组合关系本身，不承担复杂优先级或执行调度职责。

- `RecurrentQueryComposeOperator`
  作用：构建 recurrent query，并保留 years/months/days/hours 选择信息。
  类型：composite operator。
  约束：当前已表达 recurrent query 的时间模式结构，但尚未实现原项目中切片级联更新的完整运行时行为。

#### Filter operators

- `ApplySpatialFilterOperator`
  作用：对 visual data 应用空间约束过滤。
  约束：当前支持基于 query 结构和 region 参数的过滤，但仍然是逻辑 mask 计算，不是 GPU 侧过滤。

- `ApplyTemporalFilterOperator`
  作用：对 visual data 应用时间约束过滤。
  约束：与 spatial filter 平行存在，这是有意保留的边界，用于显式表达 STC 中空间过滤与时间过滤的分离。

- `CombineFiltersOperator`
  作用：合并多个过滤结果。
  类型：composite operator。
  约束：当前与 `FilterMask.Combine()` 存在轻度功能重合，后续可以收敛为单一逻辑来源。

- `UpdateViewEncodingOperator`
  作用：将 filter 结果写回 view state，并标记需要 backend sync。
  约束：当前默认假设 mask 顺序与目标 view 点顺序兼容，或者角色约束足以保证对齐；这是一种 draft-level 假设，不等同于原项目中的 texture-based propagation。

#### Backend operators

- `IAdaptedIATKAdapter`
  作用：定义 backend-facing 抽象接口。
  约束：当前接口粒度仍然较轻，主要用于表达边界，而不是覆盖完整 Adapted IATK API。

- `AdaptedIATKViewBuilderOperator`
  作用：将抽象 view 标记为 backend build spec。
  约束：当前是轻量 builder stub，用于表达 backend build phase 的存在。

- `AdaptedIATKViewOperator`
  作用：创建或更新 backend-facing view object。
  约束：当前是语义性 stub；虽然已经与 builder 分离，但两者边界仍然较近，后续可以根据真实 backend 接入深度决定是否继续拆分。

#### 当前存在的轻度重合

- `BuildPointViewOperator` / `BuildLinkViewOperator` 与 `BuildSTCViewOperator`
  判断：这是 primitive 与 composite 的组合关系，不属于无意义重复。

- `ApplySpatialFilterOperator` 与 `ApplyTemporalFilterOperator`
  判断：这是平行职责划分，不建议合并，否则会削弱 STC query 结构表达。

- `FilterMask.Combine()` 与 `CombineFiltersOperator`
  判断：存在轻度重合；后续建议统一为单一逻辑来源。

- `AdaptedIATKViewBuilderOperator` 与 `AdaptedIATKViewOperator`
  判断：边界偏近，但当前保留有助于表达 backend 的 build/update 两阶段结构。


## 5. 当前版本相对于原项目的主要保留点

### 5.1 已显式表达 OD semantics

当前版本已经不再把输入简单当作 generic point list，而是支持：

- origin / destination 点角色
- 每条记录的 `RowId`
- 自动构造 `ODLink`

这使得该 package 在概念上更接近原始 `ImmersiveTaxiVis` 的 taxi OD 语义。

### 5.2 已显式表达 STC time semantics 的基础结构

当前版本已经支持：

- 时间列
- STC mode
- 时间窗口
- 时间 metadata

虽然还没有实现原始项目中完整的时间-几何映射机制，但已经不再把时间仅仅视为普通属性列。

### 5.3 已显式表达多视图分离

当前版本中，STC、point view、2D projection、link view 已经分离建模。

其中 `BuildSTCViewOperator` 也不再把 STC 视为单一孤立 view，而是能够在存在 OD 语义时组织出协调子视图：

- origin point view
- destination point view
- link view

### 5.4 已显式表达 query family

当前版本已经对以下 query family 建模：

- atomic
- directional
- merged
- recurrent

并为 atomic、directional、recurrent 引入了更接近原项目的结构字段。

### 5.5 已保留 backend separation

当前版本没有把 view update 直接等同于“修改点集合”，而是保留了 backend adapter 抽象。

虽然现在 backend 仍是轻量 stub，但其边界已经明确。


## 6. 当前版本仍然保留为 draft 的部分

为了让这份 operator package 保持在课程 / 研究讨论稿的合理规模内，当前版本仍然有一些有意识保留的简化。

### 6.1 尚未实现原项目那种 shader-based filter propagation

当前版本没有真正实现：

- compute shader
- brushed texture
- linked view texture propagation
- IATK material channel update

因此它目前表达的是：

- filter propagation 的概念边界

而不是：

- 原型系统里的完整 GPU 实现

此外，当前版本中的 `FilterMask` 仍然采用逻辑掩码形式，`ApplyMask()` 默认假设：

- mask 与目标 view 的点顺序兼容
- 或者角色约束已经足够将其限制到正确子集

这一点对于当前 draft 是可接受的，但还不等同于原始项目中 pickup / dropoff / linking views 的完整 texture-based propagation。

### 6.2 尚未复刻原始 Unity runtime managers

当前 package 不打算重建：

- `STCManager`
- `ODSTCManager`
- `QueryManager`
- Unity scene wiring

对应的职责已经被抽象为 operator categories，而不是保留为 Unity runtime manager。

### 6.3 recurrent / directional query 仍然主要是结构性表达

当前版本已经补足了这些 query 的语义字段，但还没有完全发展到原项目中那种完整联动执行深度。

因此它们目前更适合作为：

- faithful operator-level representation

而不是：

- full execution-level reproduction


## 7. 对当前版本的定位

我认为当前版本最准确的定位是：

**一个面向 ImmersiveTaxiVis visualization core 的、结构自洽的 operator-based decomposition draft。**

它已经：

- 显式表达了 OD 双端点语义
- 明确区分了 STC、point、link、2D projection views
- 将 query 建模为对象体系
- 将 filter execution 与 query definition 分开
- 保留了 Adapted IATK backend 的独立边界

但它还没有：

- 完整重现 Unity runtime 行为
- 完整重现原项目的 compute-shader filtering backend



## 8. 总结

这份 operator package 的核心价值在于：

它把原始 `ImmersiveTaxiVis` 中较为分散、耦合在 Unity prototype 内部的 visualization core，重组为一套更清晰、显式、可分析的 operator pipeline。

当前版本已经能够较明确地保留原项目的几个关键思想：

- OD-oriented visualization
- Space-Time Cube semantics
- multi-view coordination
- query object composition
- filter-based view update
- backend separation
