import { ArrowLeft, ArrowUpRight, Compass, ExternalLink, Sparkles, Star } from 'lucide-react';
import type { Project } from './types';
import { spotlights } from './spotlight-data';

const format = (n: number) => new Intl.NumberFormat('en-US').format(n);

export default function Spotlights({ projects }: { projects: Project[] }) {
  const byName = new Map(projects.map(project => [project.fullName.toLowerCase(), project]));
  const groups = [
    { id: 'hot', title: '热度观察', note: '看本周新增 Star，再看项目带来了什么新用法。' },
    { id: 'curious', title: '玩法新意', note: '看交互和场景是否有新意，而不按 Star 排名。' },
  ] as const;

  return <div className="spotlights-page">
    <a href="#/" className="back-link"><ArrowLeft size={16} />返回榜单</a>
    <header className="spotlights-intro">
      <span className="eyebrow"><Sparkles size={14} /> PROJECT DISCOVERY</span>
      <h1>有趣项目</h1>
      <p>这里用两个维度发现项目：热度看可核对的 Star 增长；趣味看它是否带来不同的交互或使用场景。</p>
      <div className="spotlights-rule"><strong>怎样判断“有趣”？</strong><p>编辑挑选时要求能说清一个具体的新玩法，并找到公开资料或示例作为尝试入口。每张卡片都写出入选理由和第一步；没有客观的“趣味分”。</p></div>
      <span className="spotlights-note">本周新增取 GitHub 官方历史统计；它反映关注变化，不代表实际使用人数。</span>
    </header>
    {groups.map(group => {
      const entries = spotlights.filter(item => item.group === group.id).map(item => ({ item, project: byName.get(item.fullName.toLowerCase()) })).filter((entry): entry is { item: typeof entry.item; project: Project } => !!entry.project);
      if (!entries.length) return null;
      return <section className="spotlights-group" key={group.id} aria-labelledby={`spotlights-${group.id}`}>
        <div className="spotlights-heading"><div><span>{group.id === 'hot' ? <Star size={17} /> : <Compass size={17} />}</span><h2 id={`spotlights-${group.id}`}>{group.title}</h2></div><p>{group.note}</p></div>
        <div className="spotlights-grid">{entries.map(({ item, project }) => <article className="spotlight-card" key={item.fullName}>
          <div className="spotlight-card-top"><span className="spotlight-kind">{item.lens}</span><span className="spotlight-stars"><Star size={13} />累计 {format(project.stars)}</span></div>
          <h3>{item.angle}</h3><p className="spotlight-project-name">{project.fullName}</p>
          {group.id === 'hot' && <p className="spotlight-growth">{project.metrics.weekly === null ? '本周增长数据暂缺' : `本周新增 +${format(project.metrics.weekly)} Star`}</p>}
          <p className="spotlight-why"><strong>入选理由</strong>{item.why}</p>
          <p className="spotlight-start"><strong>从这里开始</strong>{item.start}</p>
          <div className="spotlight-links"><a href={'#/project/' + encodeURIComponent(project.fullName)}>了解项目 <ArrowUpRight size={15} /></a><a href={project.url} target="_blank" rel="noreferrer">GitHub <ExternalLink size={14} /></a></div>
        </article>)}</div>
      </section>;
    })}
  </div>;
}
