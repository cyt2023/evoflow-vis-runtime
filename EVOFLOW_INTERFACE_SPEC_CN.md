# ImmersiveTaxiVis Operator Package 的 EvoFlow 风格接口协议

## 1. 文档目的

本文为当前 `ImmersiveTaxiVis` visualization-core operator package 补充一层 **EvoFlow-compatible 接口协议**。

需要强调的是：

- 当前仓库中的 C# operator 是 **implementation-layer operators**
- 本文档定义的是这些 operators 在 EvoFlow / agent orchestration 体系中的 **communication-layer contract**

因此，这份文档不是在替换现有 C# 设计，而是在其外部补充一层统一的调用与返回规范，使这些 operators 可以：

- 被工作流系统追踪
- 被 manager agent 调度
- 被 critic agent 验证
- 被 Unity 或其他前端以声明式 JSON 调用


## 2. 总体设计原则

### 2.1 统一通信外壳

所有 operator 的输入与输出都应包裹统一的 wrapper 元数据：

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Map_OD_01",
  "operator_type": "Map_To_Visual_Space_Op",
  "operator_level": "Level_1",
  "timestamp": "2026-04-01T12:00:00Z"
}
```

建议公共字段如下：

- `workflow_id`
- `operator_id`
- `operator_type`
- `operator_level`
- `timestamp`
- `status`
- `payload`
- `error_info`
- `agent_reflection`

### 2.2 控制面与数据面分离

参考 EvoFlow 风格，建议将：

- 参数与上下文放在 JSON 中
- 数据本体通过 pointer / handle / cache id 传递

也就是说：

- JSON 承担 control plane
- 点集、link、mask、view bundle、backend state 等对象通过 data-plane pointer 引用

### 2.3 保留 visualization-core 语义

由于本 package 对应的是 `ImmersiveTaxiVis` 的 visualization core，因此接口协议必须保留以下语义：

- OD 双端点
- STC 时间语义
- multi-view separation
- query family
- filter propagation
- backend separation

因此，这套协议不能退化成 generic table-processing schema。


## 3. 分层约定

为了与 EvoFlow 风格保持一致，同时又贴合当前项目，建议采用以下四层：

- `Level_1`: Data Transformation
- `Level_2`: Visual Encoding / View Construction
- `Level_3`: Query / Filter / Interaction Binding
- `Level_4`: Workflow Assembly / Composite Pipeline

说明：

- 当前 `ImmersiveTaxiVis` package 没有完整实现动态 UI 注入与运行时交互控制，所以这里的 `Level_3` 主要对应 query/filter/update 语义
- 若未来接入 Unity runtime declarative UI，再可继续扩展真正的 interaction operators


## 4. 标准输入输出骨架

### 4.1 标准输入格式

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Read_Data_01",
  "operator_type": "Read_Data_Op",
  "operator_level": "Level_1",
  "timestamp": "2026-04-01T12:00:00Z",
  "input_data": {},
  "parameters": {}
}
```

### 4.2 标准成功输出格式

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Read_Data_01",
  "operator_type": "Read_Data_Op",
  "operator_level": "Level_1",
  "status": "success",
  "timestamp": "2026-04-01T12:00:01Z",
  "payload": {},
  "agent_reflection": "已完成数据读取。"
}
```

### 4.3 标准失败输出格式

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Read_Data_01",
  "operator_type": "Read_Data_Op",
  "operator_level": "Level_1",
  "status": "failed",
  "timestamp": "2026-04-01T12:00:01Z",
  "error_info": {
    "error_category": "FileNotFound",
    "message": "输入文件不存在",
    "details": "Assets/Data/nyc_taxi_sample.csv"
  },
  "critic_feedback": "请检查输入路径是否正确，或确认缓存文件是否已生成。"
}
```


## 5. 与当前 C# operators 的映射

### 5.1 Level 1: Data Transformation

这一层对应当前 package 的：

- `ReadDataOperator`
- `FilterRowsOperator`
- `NormalizeAttributesOperator`
- `EncodeTimeOperator`
- `MapToVisualSpaceOperator`

---

### 5.1.1 Read_Data_Op

对应：

- [ReadDataOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Data/ReadDataOperator.cs)

功能：

- 从 CSV 或其他表格式输入中读取原始 tabular OD 数据

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Read_Data_01",
  "operator_type": "Read_Data_Op",
  "operator_level": "Level_1",
  "timestamp": "2026-04-01T12:00:00Z",
  "input_data": {
    "source_path": "Data/cache/nyc_taxi_sample.csv"
  },
  "parameters": {
    "format": "csv",
    "has_header": true
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Read_Data_01",
  "operator_type": "Read_Data_Op",
  "operator_level": "Level_1",
  "status": "success",
  "timestamp": "2026-04-01T12:00:01Z",
  "payload": {
    "data_plane": {
      "tabular_pointer": "Cache/tabular/taxi_table_01.json"
    },
    "meta_data": {
      "row_count": 120000,
      "column_count": 12
    }
  },
  "agent_reflection": "已完成原始 OD 表格数据读取。"
}
```

---

### 5.1.2 Encode_Time_Op

对应：

- [EncodeTimeOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Data/EncodeTimeOperator.cs)

功能：

- 将时间列编码为 STC 可用的数值形式
- 保留时间范围 metadata

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Encode_Time_01",
  "operator_type": "Encode_Time_Op",
  "operator_level": "Level_1",
  "timestamp": "2026-04-01T12:01:00Z",
  "input_data": {
    "tabular_pointer": "Cache/tabular/taxi_table_01.json"
  },
  "parameters": {
    "time_column": "pickup_datetime",
    "output_column": "EncodedPickupTime"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Encode_Time_01",
  "operator_type": "Encode_Time_Op",
  "operator_level": "Level_1",
  "status": "success",
  "timestamp": "2026-04-01T12:01:02Z",
  "payload": {
    "data_plane": {
      "tabular_pointer": "Cache/tabular/taxi_table_pickup_time_encoded.json"
    },
    "meta_data": {
      "time_min": "2013-01-01T00:00:00Z",
      "time_max": "2013-01-31T23:59:59Z",
      "output_column": "EncodedPickupTime"
    }
  }
}
```

---

### 5.1.3 Map_To_Visual_Space_Op

对应：

- [MapToVisualSpaceOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Data/MapToVisualSpaceOperator.cs)

功能：

- 将原始 OD 表格映射为 visualization-core 数据
- 支持 origin / destination 两端点
- 支持 STC 时间轴
- 自动构建 OD links

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Map_OD_01",
  "operator_type": "Map_To_Visual_Space_Op",
  "operator_level": "Level_1",
  "timestamp": "2026-04-01T12:03:00Z",
  "input_data": {
    "tabular_pointer": "Cache/tabular/taxi_table_full_encoded.json"
  },
  "parameters": {
    "trip_id_column": "trip_id",
    "origin_x_column": "pickup_longitude",
    "origin_y_column": "pickup_latitude",
    "origin_time_column": "EncodedPickupTime",
    "destination_x_column": "dropoff_longitude",
    "destination_y_column": "dropoff_latitude",
    "destination_time_column": "EncodedDropoffTime",
    "color_column": "fare_amount",
    "size_column": "passenger_count",
    "stc_mode": true
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Map_OD_01",
  "operator_type": "Map_To_Visual_Space_Op",
  "operator_level": "Level_1",
  "status": "success",
  "timestamp": "2026-04-01T12:03:03Z",
  "payload": {
    "data_plane": {
      "visual_data_pointer": "Cache/visual/od_visual_data_01.json"
    },
    "meta_data": {
      "origin_point_count": 120000,
      "destination_point_count": 120000,
      "link_count": 120000,
      "has_od_semantics": true,
      "has_stc_time_semantics": true
    }
  },
  "agent_reflection": "已将 OD 表格映射为双端点与 link 结构。"
}
```


## 6. Level 2: Visual Encoding / View Construction

这一层对应当前 package 的：

- `BuildPointViewOperator`
- `BuildSTCViewOperator`
- `Build2DProjectionViewOperator`
- `BuildLinkViewOperator`
- `AdaptedIATKViewBuilderOperator`

---

### 6.1 Build_Point_View_Op

对应：

- [BuildPointViewOperator.cs](/Users/cyt/Desktop/OperatorsDraft/View/BuildPointViewOperator.cs)

功能：

- 构建 origin 或 destination 的点视图表示

说明：

- 这是 primitive view operator
- 它通常被更高层的 STC 组合算子复用

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_Point_Origin_01",
  "operator_type": "Build_Point_View_Op",
  "operator_level": "Level_2",
  "timestamp": "2026-04-01T12:05:00Z",
  "input_data": {
    "visual_data_pointer": "Cache/visual/od_visual_data_01.json"
  },
  "parameters": {
    "role": "Origin",
    "view_name": "STC-OriginView"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_Point_Origin_01",
  "operator_type": "Build_Point_View_Op",
  "operator_level": "Level_2",
  "status": "success",
  "timestamp": "2026-04-01T12:05:01Z",
  "payload": {
    "data_plane": {
      "view_pointer": "Cache/views/stc_origin_view_01.json"
    },
    "meta_data": {
      "view_type": "Point",
      "role": "Origin"
    }
  }
}
```

---

### 6.2 Build_Link_View_Op

对应：

- [BuildLinkViewOperator.cs](/Users/cyt/Desktop/OperatorsDraft/View/BuildLinkViewOperator.cs)

功能：

- 构建 OD 连接视图

说明：

- 这是 primitive view operator
- 它通常与 origin/destination point views 一起组成 STC 视图 bundle

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_Link_01",
  "operator_type": "Build_Link_View_Op",
  "operator_level": "Level_2",
  "timestamp": "2026-04-01T12:06:00Z",
  "input_data": {
    "visual_data_pointer": "Cache/visual/od_visual_data_01.json"
  },
  "parameters": {
    "view_name": "STC-LinkView"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_Link_01",
  "operator_type": "Build_Link_View_Op",
  "operator_level": "Level_2",
  "status": "success",
  "timestamp": "2026-04-01T12:06:01Z",
  "payload": {
    "data_plane": {
      "view_pointer": "Cache/views/stc_link_view_01.json"
    },
    "meta_data": {
      "view_type": "Link",
      "link_count": 120000
    }
  }
}
```

---

### 6.3 Build_STC_View_Bundle_Op

对应：

- [BuildSTCViewOperator.cs](/Users/cyt/Desktop/OperatorsDraft/View/BuildSTCViewOperator.cs)

功能：

- 构建 STC 核心视图 bundle
- 组织 origin point view、destination point view、link view

说明：

- 这是 composite operator
- 它不试图取代 primitive point/link view operators，而是显式地组合它们

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_STC_01",
  "operator_type": "Build_STC_View_Bundle_Op",
  "operator_level": "Level_2",
  "timestamp": "2026-04-01T12:08:00Z",
  "input_data": {
    "visual_data_pointer": "Cache/visual/od_visual_data_01.json"
  },
  "parameters": {
    "bundle_name": "STCView"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_STC_01",
  "operator_type": "Build_STC_View_Bundle_Op",
  "operator_level": "Level_2",
  "status": "success",
  "timestamp": "2026-04-01T12:08:02Z",
  "payload": {
    "data_plane": {
      "view_bundle_pointer": "Cache/views/stc_bundle_01.json"
    },
    "meta_data": {
      "bundle_type": "STC",
      "coordinated_views": [
        "STC-OriginView",
        "STC-DestinationView",
        "STC-LinkView"
      ]
    }
  }
}
```

---

### 6.4 Build_2D_Projection_View_Op

对应：

- [Build2DProjectionViewOperator.cs](/Users/cyt/Desktop/OperatorsDraft/View/Build2DProjectionViewOperator.cs)

功能：

- 构建 spatial projection 或 temporal projection view

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_Projection_01",
  "operator_type": "Build_2D_Projection_View_Op",
  "operator_level": "Level_2",
  "timestamp": "2026-04-01T12:09:00Z",
  "input_data": {
    "visual_data_pointer": "Cache/visual/od_visual_data_01.json"
  },
  "parameters": {
    "projection_kind": "Spatial",
    "plane": "XY",
    "role": "Origin",
    "view_name": "Spatial-OriginProjection"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_Build_Projection_01",
  "operator_type": "Build_2D_Projection_View_Op",
  "operator_level": "Level_2",
  "status": "success",
  "timestamp": "2026-04-01T12:09:01Z",
  "payload": {
    "data_plane": {
      "view_pointer": "Cache/views/spatial_origin_projection_01.json"
    },
    "meta_data": {
      "view_type": "Projection2D",
      "projection_kind": "Spatial",
      "plane": "XY",
      "role": "Origin"
    }
  }
}
```

---

### 6.5 Adapted_IATK_View_Builder_Op

对应：

- [AdaptedIATKViewBuilderOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Backend/AdaptedIATKViewBuilderOperator.cs)
- [AdaptedIATKViewOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Backend/AdaptedIATKViewOperator.cs)

功能：

- 将抽象 view 转换为 backend-facing view description

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_IATK_Build_01",
  "operator_type": "Adapted_IATK_View_Builder_Op",
  "operator_level": "Level_2",
  "timestamp": "2026-04-01T12:10:00Z",
  "input_data": {
    "view_pointer": "Cache/views/stc_origin_view_01.json"
  },
  "parameters": {
    "backend": "AdaptedIATK"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L2_IATK_Build_01",
  "operator_type": "Adapted_IATK_View_Builder_Op",
  "operator_level": "Level_2",
  "status": "success",
  "timestamp": "2026-04-01T12:10:01Z",
  "payload": {
    "data_plane": {
      "backend_view_pointer": "Cache/backend/iatk_view_origin_01.json"
    },
    "meta_data": {
      "backend": "AdaptedIATK",
      "backend_build_pending": false
    }
  }
}
```


## 7. Level 3: Query / Filter / View Update

这一层对应当前 package 的：

- `CreateAtomicQueryOperator`
- `CreateDirectionalQueryOperator`
- `MergeQueriesOperator`
- `RecurrentQueryComposeOperator`
- `ApplySpatialFilterOperator`
- `ApplyTemporalFilterOperator`
- `CombineFiltersOperator`
- `UpdateViewEncodingOperator`

---

### 7.1 Create_Atomic_Query_Op

对应：

- [CreateAtomicQueryOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Query/CreateAtomicQueryOperator.cs)

功能：

- 创建 atomic query
- 支持 `Origin / Destination / Either`
- 支持空间区域与时间窗口

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Atomic_Query_01",
  "operator_type": "Create_Atomic_Query_Op",
  "operator_level": "Level_3",
  "timestamp": "2026-04-01T12:12:00Z",
  "input_data": {
    "spatial_region": {
      "min_x": 0.2,
      "max_x": 0.4,
      "min_y": 0.3,
      "max_y": 0.5,
      "min_time": 1000.0,
      "max_time": 8000.0
    }
  },
  "parameters": {
    "mode": "Origin",
    "shape": "Prism"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Atomic_Query_01",
  "operator_type": "Create_Atomic_Query_Op",
  "operator_level": "Level_3",
  "status": "success",
  "timestamp": "2026-04-01T12:12:01Z",
  "payload": {
    "data_plane": {
      "query_pointer": "Cache/query/atomic_origin_01.json"
    },
    "meta_data": {
      "query_type": "Atomic",
      "atomic_mode": "Origin"
    }
  }
}
```

---

### 7.2 Create_Directional_Query_Op

对应：

- [CreateDirectionalQueryOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Query/CreateDirectionalQueryOperator.cs)

功能：

- 将 origin query 与 destination query 组合成 directional query

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Directional_Query_01",
  "operator_type": "Create_Directional_Query_Op",
  "operator_level": "Level_3",
  "timestamp": "2026-04-01T12:13:00Z",
  "input_data": {
    "origin_query_pointer": "Cache/query/atomic_origin_01.json",
    "destination_query_pointer": "Cache/query/atomic_destination_01.json"
  },
  "parameters": {
    "combine_mode": "OriginAndDestination"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Directional_Query_01",
  "operator_type": "Create_Directional_Query_Op",
  "operator_level": "Level_3",
  "status": "success",
  "timestamp": "2026-04-01T12:13:01Z",
  "payload": {
    "data_plane": {
      "query_pointer": "Cache/query/directional_01.json"
    },
    "meta_data": {
      "query_type": "Directional",
      "direction_semantics": "OD"
    }
  },
  "agent_reflection": "已组合 origin 与 destination query，形成定向 OD 查询。"
}
```

---

### 7.3 Recurrent_Query_Compose_Op

对应：

- [RecurrentQueryComposeOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Query/RecurrentQueryComposeOperator.cs)

功能：

- 创建 recurrent query
- 保留时间模式选择信息

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Recurrent_Query_01",
  "operator_type": "Recurrent_Query_Compose_Op",
  "operator_level": "Level_3",
  "timestamp": "2026-04-01T12:14:00Z",
  "input_data": {
    "subquery_pointers": [
      "Cache/query/atomic_origin_01.json"
    ]
  },
  "parameters": {
    "months": [1, 2],
    "days_of_week": ["Monday", "Tuesday"],
    "hours": [8, 9, 10]
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Recurrent_Query_01",
  "operator_type": "Recurrent_Query_Compose_Op",
  "operator_level": "Level_3",
  "status": "success",
  "timestamp": "2026-04-01T12:14:01Z",
  "payload": {
    "data_plane": {
      "query_pointer": "Cache/query/recurrent_01.json"
    },
    "meta_data": {
      "query_type": "Recurrent",
      "months": [1, 2],
      "hours": [8, 9, 10]
    }
  }
}
```

---

### 7.4 Apply_Spatial_Filter_Op

对应：

- [ApplySpatialFilterOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Filter/ApplySpatialFilterOperator.cs)

功能：

- 对 visual data 应用空间 filter

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Apply_Spatial_Filter_01",
  "operator_type": "Apply_Spatial_Filter_Op",
  "operator_level": "Level_3",
  "timestamp": "2026-04-01T12:15:00Z",
  "input_data": {
    "visual_data_pointer": "Cache/visual/od_visual_data_01.json",
    "query_pointer": "Cache/query/atomic_origin_01.json"
  },
  "parameters": {}
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Apply_Spatial_Filter_01",
  "operator_type": "Apply_Spatial_Filter_Op",
  "operator_level": "Level_3",
  "status": "success",
  "timestamp": "2026-04-01T12:15:02Z",
  "payload": {
    "data_plane": {
      "mask_pointer": "Cache/filter/spatial_mask_origin_01.json"
    },
    "meta_data": {
      "selected_count": 8420,
      "target_role": "Origin"
    }
  }
}
```

---

### 7.5 Apply_Temporal_Filter_Op

对应：

- [ApplyTemporalFilterOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Filter/ApplyTemporalFilterOperator.cs)

功能：

- 对 visual data 应用时间 filter

Output 示例：

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Apply_Temporal_Filter_01",
  "operator_type": "Apply_Temporal_Filter_Op",
  "operator_level": "Level_3",
  "status": "success",
  "timestamp": "2026-04-01T12:16:02Z",
  "payload": {
    "data_plane": {
      "mask_pointer": "Cache/filter/temporal_mask_origin_01.json"
    },
    "meta_data": {
      "selected_count": 5310,
      "target_role": "Origin"
    }
  }
}
```

---

### 7.6 Combine_Filters_Op

对应：

- [CombineFiltersOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Filter/CombineFiltersOperator.cs)

功能：

- 将空间与时间 filter 合并

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Combine_Filter_01",
  "operator_type": "Combine_Filters_Op",
  "operator_level": "Level_3",
  "timestamp": "2026-04-01T12:17:00Z",
  "input_data": {
    "mask_pointers": [
      "Cache/filter/spatial_mask_origin_01.json",
      "Cache/filter/temporal_mask_origin_01.json"
    ]
  },
  "parameters": {
    "mode": "AND"
  }
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Combine_Filter_01",
  "operator_type": "Combine_Filters_Op",
  "operator_level": "Level_3",
  "status": "success",
  "timestamp": "2026-04-01T12:17:01Z",
  "payload": {
    "data_plane": {
      "mask_pointer": "Cache/filter/combined_mask_origin_01.json"
    },
    "meta_data": {
      "mode": "AND",
      "selected_count": 4178
    }
  }
}
```

---

### 7.7 Update_View_Encoding_Op

对应：

- [UpdateViewEncodingOperator.cs](/Users/cyt/Desktop/OperatorsDraft/Filter/UpdateViewEncodingOperator.cs)

功能：

- 将 filter 结果应用到 view state
- 标记需要 backend 同步

约束说明：

- 当前版本默认假设 `mask_pointer` 对应的逻辑顺序与 `view_pointer` 中目标点集的顺序兼容
- 若 view 是从完整 OD 数据裁剪得到的子视图，则应依赖 role 约束或上游对齐策略保证一致性
- 这是一种 draft-level 假设，不等同于原始 `ImmersiveTaxiVis` 中基于多纹理的严格传播机制

Input:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Update_View_Encoding_01",
  "operator_type": "Update_View_Encoding_Op",
  "operator_level": "Level_3",
  "timestamp": "2026-04-01T12:18:00Z",
  "input_data": {
    "view_pointer": "Cache/views/stc_origin_view_01.json",
    "mask_pointer": "Cache/filter/combined_mask_origin_01.json"
  },
  "parameters": {}
}
```

Output:

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L3_Update_View_Encoding_01",
  "operator_type": "Update_View_Encoding_Op",
  "operator_level": "Level_3",
  "status": "success",
  "timestamp": "2026-04-01T12:18:01Z",
  "payload": {
    "data_plane": {
      "view_pointer": "Cache/views/stc_origin_view_01.json"
    },
    "meta_data": {
      "selected_count": 4178,
      "requires_backend_sync": true,
      "filter_target_role": "Origin"
    }
  }
}
```


## 8. Level 4: Composite Workflow Assembly

当前 package 虽然没有单独实现 workflow manager 类，但从 EvoFlow 角度，完全可以把这些 operators 组装为 DAG。

示例：`OD STC Query Pipeline`

```json
{
  "workflow_id": "wf_taxivis_001",
  "workflow_type": "OD_STC_Query_Pipeline",
  "execution_graph": {
    "nodes": [
      {"id": "op_read", "type": "Read_Data_Op", "level": "L1"},
      {"id": "op_encode_pickup", "type": "Encode_Time_Op", "level": "L1"},
      {"id": "op_encode_dropoff", "type": "Encode_Time_Op", "level": "L1"},
      {"id": "op_map", "type": "Map_To_Visual_Space_Op", "level": "L1"},
      {"id": "op_build_stc", "type": "Build_STC_View_Bundle_Op", "level": "L2"},
      {"id": "op_query", "type": "Create_Atomic_Query_Op", "level": "L3"},
      {"id": "op_filter_space", "type": "Apply_Spatial_Filter_Op", "level": "L3"},
      {"id": "op_filter_time", "type": "Apply_Temporal_Filter_Op", "level": "L3"},
      {"id": "op_filter_merge", "type": "Combine_Filters_Op", "level": "L3"},
      {"id": "op_update", "type": "Update_View_Encoding_Op", "level": "L3"},
      {"id": "op_backend", "type": "Adapted_IATK_View_Builder_Op", "level": "L2"}
    ],
    "edges": [
      {"from": "op_read", "to": "op_encode_pickup"},
      {"from": "op_read", "to": "op_encode_dropoff"},
      {"from": "op_encode_pickup", "to": "op_map"},
      {"from": "op_encode_dropoff", "to": "op_map"},
      {"from": "op_map", "to": "op_build_stc"},
      {"from": "op_build_stc", "to": "op_update"},
      {"from": "op_query", "to": "op_filter_space"},
      {"from": "op_query", "to": "op_filter_time"},
      {"from": "op_filter_space", "to": "op_filter_merge"},
      {"from": "op_filter_time", "to": "op_filter_merge"},
      {"from": "op_filter_merge", "to": "op_update"},
      {"from": "op_update", "to": "op_backend"}
    ]
  }
}
```


## 9. Critic / Verification 建议

如果未来要接 EvoFlow critic agent，建议至少验证以下几类错误：

- `MissingColumn`
- `InvalidRole`
- `InvalidTimeWindow`
- `BrokenODSemantics`
- `MaskViewMismatch`
- `BackendSyncFailure`

示例：

```json
{
  "workflow_id": "wf_taxivis_001",
  "operator_id": "L1_Map_OD_01",
  "operator_type": "Critic_Verification",
  "status": "failed",
  "error_info": {
    "error_category": "MissingColumn",
    "message": "找不到 destination_time_column",
    "details": "EncodedDropoffTime"
  },
  "critic_feedback": "请检查 dropoff 时间编码步骤是否已经执行，或确认映射参数中的列名是否一致。"
}
```


## 10. 这份协议与当前 C# 实现的关系

这份协议文档不意味着当前 C# code 已经完整支持上述所有 runtime 行为。

更准确地说：

- 当前 C# code 提供了 operator-level 内部结构
- 本文档定义了这些 operator 在 EvoFlow 环境中的外部接口形式

所以它们的关系是：

**C# classes = implementation model**

**JSON protocol = orchestration contract**

两者不是替代关系，而是上下层关系。
