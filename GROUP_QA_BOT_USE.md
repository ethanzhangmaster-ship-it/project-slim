# Group QA Bot Use

## 当前能力

- 固定指令
  - `@机器人 帮助`
  - `@机器人 简版`
  - `@机器人 详细版`
  - `@机器人 回收版`
  - `@机器人 老板版`
  - `@机器人 摘要`
  - `@机器人 发送市场版`
  - `@机器人 发送详细市场版`
  - `@机器人 发送回收版`
  - `@机器人 发送老板版`

- 直接问答
  - `@机器人 本周ROI多少？`
  - `@机器人 现在能发吗？`
  - `@机器人 当前回调地址是什么？`
  - `@机器人 P04为什么有风险？`

- 需求记录
  - `@机器人 把老板版文案再压缩一点`
  - `@机器人 把市场版第一页再压缩一点`
  - `@机器人 把回收版标题改短一点`

- 需求补充
  - `@机器人 补充：重点突出最大风险项目`

- 待办查看
  - `@机器人 最新待办`
  - `@机器人 最近待办`
  - `@机器人 待办 req_xxx`

- 待办状态
  - `@机器人 确认待办 req_xxx`
  - `@机器人 开始处理 req_xxx`
  - `@机器人 批准待办 req_xxx`
  - `@机器人 驳回待办 req_xxx`
  - `@机器人 完成待办 req_xxx`
  - `@机器人 关闭待办 req_xxx`

- 待办管理增强
  - `@机器人 已确认待办`
  - `@机器人 进行中待办`
  - `@机器人 已批准任务`
  - `@机器人 执行已批准任务`
  - `@机器人 待办统计`
  - `@机器人 执行清单`
  - `@机器人 老板版待办`
  - `@机器人 市场版待办`
  - `@机器人 回收版待办`
  - `@机器人 机器人待办`
  - `@机器人 高风险待办`
  - `@机器人 林凯待办`
  - `@机器人 牟耕待办`
  - `@机器人 姜会伟待办`
  - `@机器人 正式任务包`
  - `@机器人 待审批执行单`
  - `@机器人 已批准任务清单`
  - `@机器人 最近发送记录`

## 数据落点

- 待办队列
  - `output/active/group_requirements_queue.json`

- 执行清单
  - `output/active/group_execution_checklist_latest.md`

- 正式任务包
  - `output/active/group_task_packet_latest.md`

- 待审批执行单
  - `output/active/group_approval_packet_latest.md`

- 已批准任务清单
  - `output/active/group_approved_tasks_latest.md`

- 已批准执行结果
  - `output/active/group_approved_execution_latest.md`
  - `output/active/group_approved_execution_latest.json`

- 发送记录
  - `output/active/group_send_log_latest.md`
  - `output/active/group_send_log_latest.json`

## 当前边界

- 可以
  - 回答当前系统状态和周报问题
  - 记录需求
  - 补充需求
  - 查询待办
  - 更新待办状态
  - 生成执行清单、审批单、已批准任务清单
  - 在通过门禁后触发正式发送

- 不可以
  - 直接改 `.env`
  - 直接改 webhook
  - 直接改白名单
  - 直接改发送目标群
  - 直接改定时任务
  - 直接执行系统变更

## 外部风险

- 当前公网回调仍依赖临时 `trycloudflare` 地址。
- 如果群里突然没有回复，优先检查：
  - `output/active/feishu_callback_live.txt`
- 机器人逻辑和本地回调服务已经打通；不稳定主要来自临时公网入口。

## 已批准后的执行入口

- 本地执行命令
  - `python -m market_ops.cli group-approved-execute --report-date latest`

- 作用
  - 读取已批准待办
  - 按 scope 重生成对应周报预览
  - 产出执行结果文件
  - 将已执行的待办状态更新为 `done`
