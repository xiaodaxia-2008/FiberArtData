# Models — 仿真环境组件模型库

搭建仿真环境常用的场景组件模型，全部为 **assimp 可直接导入**的格式
（DAE / OBJ / FBX / GLB，均已用 FiberArt 同款 assimp vc143 构建实测导入通过）。

## 目录结构

```
Models/
├── Table/                      # 桌子
│   ├── CafeTable/              #   咖啡桌（Gazebo，DAE + 木纹贴图）
│   └── KenneyFurnitureKit/     #   Kenney 家具包桌类（OBJ/FBX/DAE 三格式）
├── Fence/
│   └── KenneyCityKit/          # 围栏，9 种尺寸（OBJ/FBX/GLB 三格式）
├── Human/
│   ├── PersonStanding/         # 站立人体（Gazebo，DAE + 贴图）
│   └── PersonWalking/          # 行走人体（Gazebo，DAE + 贴图）
├── ElectricalCabinet/
│   ├── ControlConsole/         # 电控台/控制柜（Gazebo，DAE + 贴图）
│   └── SwitchBoard.fbx         # 配电柜（MIT，FBX）
└── Props/                      # 常用道具
    ├── EuroPallet/             #   欧式托盘
    ├── JerseyBarrier/          #   公路隔离墩
    ├── ConstructionCone/       #   施工锥桶
    └── CardboardBox/           #   纸箱
```

## 各模型明细

| 分类 | 模型 | 文件 | 格式 | 来源 | 许可证 |
|------|------|------|------|------|--------|
| Table | CafeTable 咖啡桌 | `meshes/cafe_table.dae` | DAE | [osrf/gazebo_models](https://github.com/osrf/gazebo_models) | CC BY 3.0 |
| Table | Kenney 家具包桌类：table / tableRound / tableCoffee / tableGlass / desk / sideTable 等 | `OBJ_format/*.obj` `FBX_format/*.fbx` `DAE_format/*.dae` | OBJ/FBX/DAE | [Kenney.nl Furniture Kit](https://kenney.nl/assets/furniture-kit) | CC0 |
| Fence | Kenney 围栏：fence / fence-1x2 … fence-3x3 / fence-low | `OBJ_format/fence*.obj` `FBX_format/fence*.fbx` `GLB_format/fence*.glb` | OBJ/FBX/GLB | [Kenney.nl City Kit (Suburban)](https://kenney.nl/assets/city-kit-suburban) | CC0 |
| Human | PersonStanding 站立人体 | `meshes/standing.dae` | DAE | osrf/gazebo_models | CC BY 3.0 |
| Human | PersonWalking 行走人体 | `meshes/walking.dae` | DAE | osrf/gazebo_models | CC BY 3.0 |
| ElectricalCabinet | ControlConsole 电控台 | `meshes/console.dae` | DAE | osrf/gazebo_models | CC BY 3.0 |
| ElectricalCabinet | SwitchBoard 配电柜 | `SwitchBoard.fbx` | FBX | [cgaueb/light_probe_placement](https://github.com/cgaueb/light_probe_placement) | MIT |
| Props | EuroPallet 欧式托盘 | `meshes/pallet.dae` | DAE | osrf/gazebo_models | CC BY 3.0 |
| Props | JerseyBarrier 隔离墩 | `meshes/jersey_barrier.dae` | DAE | osrf/gazebo_models | CC BY 3.0 |
| Props | ConstructionCone 锥桶 | `meshes/construction_cone.dae` | DAE | osrf/gazebo_models | CC BY 3.0 |
| Props | CardboardBox 纸箱 | `meshes/cardboard_box.dae` | DAE | osrf/gazebo_models | CC BY 3.0 |

## 许可证与署名

- **CC0（Kenney.nl 资产）**：无需署名，可自由商用。来源 [kenney.nl](https://kenney.nl/)。
- **CC BY 3.0（Gazebo 模型，原作者 Nathan Koenig / Open Source Robotics Foundation）**：
  允许商用，但**必须保留署名**。在程序"关于/模型来源"等处注明：
  *"Models from the Gazebo model database (github.com/osrf/gazebo_models),
  CC BY 3.0, Copyright 2012 Nathan Koenig."*
- **MIT（SwitchBoard.fbx，来源 cgaueb/light_probe_placement）**：允许商用，保留版权声明即可。

## 说明

- Gazebo 模型保留原始 `model.config` / `model.sdf`，其 `meshes/`、`materials/`
  目录结构与上游一致；DAE 内贴图引用已统一修正为相对 DAE 文件的正确路径
  （`../materials/textures/...`），可直接被 assimp 按默认规则解析。
- Kenney 资产每种模型提供多格式副本：OBJ（带 MTL/顶点色）、FBX、GLB（自包含），
  可按需选用；GLB 单文件自包含贴图，最省事。
- 所有网格已用真实 assimp（FiberArt 构建的 assimp-vc143-mt.dll）逐文件导入验证。
