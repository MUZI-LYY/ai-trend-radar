export type Spotlight = {
  fullName: string;
  group: 'hot' | 'curious';
  lens: string;
  angle: string;
  why: string;
  start: string;
};

// Editorial choices are independent of the Star ranking. Keep the project name
// aligned with the collected GitHub data so every card links to a real profile.
export const spotlights: Spotlight[] = [
  {
    fullName: 'openclaw/openclaw', group: 'hot', lens: '入口变化', angle: '把 AI 助手带进日常聊天',
    why: '它把消息渠道、工具和模型连接到同一个个人助手，适合观察 Agent 怎样从演示走向日常使用。',
    start: '先看 Gateway 与消息渠道的工作方式。',
  },
  {
    fullName: 'browser-use/browser-use', group: 'hot', lens: '任务玩法', angle: '让 Agent 操作网页',
    why: '网页是大量真实任务的入口；这个项目展示了智能体怎样在浏览器里观察、点击和完成步骤。',
    start: '从仓库示例了解一次完整的浏览器任务。',
  },
  {
    fullName: 'Comfy-Org/ComfyUI', group: 'hot', lens: '可视化创作', angle: '把生成过程变成可编辑工作流',
    why: '节点界面让图像与多模态生成的每一步都能看见、调整和复用，比只输入提示词更适合探索流程。',
    start: '先看一个官方示例工作流及其输入输出。',
  },
  {
    fullName: 'koala73/worldmonitor', group: 'curious', lens: '信息体验', angle: '像看地图一样看世界动态',
    why: '它把新闻、市场和地理信号放进同一张看板，提供了一种不同于时间线的信息浏览方式。',
    start: '打开项目演示，观察各类信号如何关联。',
  },
  {
    fullName: 'SillyTavern/SillyTavern', group: 'curious', lens: '角色互动', angle: '可塑造角色的多模型聊天前端',
    why: '角色设定、世界信息和扩展能力让聊天界面变成可搭建的交互体验，值得从产品设计角度拆解。',
    start: '先看角色卡与世界信息的组织方式。',
  },
  {
    fullName: 'ringhyacinth/Star-Office-UI', group: 'curious', lens: '拟人化状态', angle: '让 Agent 在像素办公室里上班',
    why: '它把空闲、写作、研究和出错等状态映射到办公室区域，让抽象的 Agent 工作变成能看见的场景。',
    start: '先看页面中的办公室状态，再读它怎样连接 Agent。',
  },
];
