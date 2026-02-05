- [ ] 将MinerU解析文件视为一个独立的操作，不在load_literature工具中进行解析(太慢了)。
  - VSCode文件系统监听发现papers目录下的文件变化，如果文件变化，则提示用户调用MinerU解析文件
- [ ] 接入TODO List功能
- [ ] 实现参数预填充功能，解决部分模块需要一些无法由LLM生成的参数的问题

Bug:
- [ ] 前端还是会显示最后一个 complete 事件
- [ ] experiment_config 迭代过程无法修复错误，只有 5 次均失败才思考并修复问题。
  e.g. experiment_config: 已执行 - 进度: 1/5 | 错误: Unknown environment module type: OnlinePlatform. Available types: ['global_information', 'economy_space', 'simple_social_space', 'mobility_space', 'reputation_game', 'commons_tragedy', 'public_goods', 'prisoners_dilemma', 'trust_game', 'volunteer_dilemma', 'social_media']

TODO:
- [ ] 实验执行和分析SubAgent（进行中）
  - [x] 假设和配置生成完成后能通过 experiment_runner 启动实验，虽然这之间生成的代码存在问题，不过状态能正确传递。