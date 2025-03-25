---
title: FiberArt 软件模型库使用说明
description: FiberArt 软件模型库
hide:
    - navigation
date:
    created: 2025-03-25T15:57:41+08:00
---

这里存放FiberArt软件使用的一些模型数据，包括机器人、工具、导轨、变位机，以及CAD曲面模型等。

## 怎么制作机器人URDF模型

### URDF

参考[这个视频教程](https://www.bilibili.com/video/BV11c411n7pN/?spm_id_from=333.999.0.0&vd_source=78eee00c318e9cda7f951c976a72c2b9)

其他值得浏览的URDF教程:

- [urdf_tutorial: Learning URDF Step by Step](https://github.com/ros/urdf_tutorial)
- [什么是URDF以及怎么理解一个URDF文件](https://blog.csdn.net/zhelijun/article/details/102709150)

### 运动学参数

FiberArt实现了两个逆运动学求解算法，一个是基于[opw_kinematics](https://github.com/Jmeyer1292/opw_kinematics)的解析算法，它的速度更快；另一个是基于雅可比的数值迭代算法。

要使用OPW解析算法，需要机械臂满足对应的构型结构（大多数工业串联六轴机械臂都满足），同时在机器人的URDF文档里面写入 `opw_parameters`：

- [怎么从机器人技术手册计算OPW参数](./opw.md)
- 怎么将OPW参数写入到机器人的URDF文档，可以参考下面的例子：

    ??? example "URDF 参考"
        ```xml
        --8<-- "Robots\KR480R3330MT\KR480R3330MT.urdf"
        ```

## 怎么制作导轨、变位机模型

导轨、变位机本质和机器人一样，可以看作是只有一个自由度的机械臂，它们的模型描述文件是一样的。在FiberArt里面为了便于区分，导轨URDF文件的后缀是 `.track`，变位机URDF文件的后缀是 `.positioner`。

## 怎么制作工具模型

机械臂法兰盘安装的末端工具也可以看作是一个机械臂，工具可能拥有内部的运动自由度（Jointed Tool，比如可以开合的夹爪）或者没有内部运动的自由度（Jointless Tool，比如焊枪），工具也是使用URDF格式的文档进行描述，只不过会比普通机器人多一些参数，比如 `attach_pose`等。FiberArt还自定义了一些其他工具，比如`3d_camera`，它的作用是在模型树上根据工具类型的不同，可以实现一些节点的额外属性，比如开启/关闭FOV等，用来模拟3D相机的拍照行为。

## 问题反馈

请通过Github Issues 或者 Email 发送问题反馈，感谢您的支持：

- [Github Issues](https://github.com/xiaodaxia-2008/FiberArtData/issues)
- Email: <fiberart@duck.com>

## 贡献

欢迎通过 PR 提交新的模型数据！
