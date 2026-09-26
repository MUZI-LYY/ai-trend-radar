import type {Dataset, Project} from './types';

// Historical observations stay intact; descriptions describe the current project.
const profileFields = [
 'category', 'related', 'kind', 'tags', 'ways', 'summary', 'overview', 'audience',
 'features', 'useCases', 'gettingStarted', 'requirements', 'usage', 'caveat',
 'editorial', 'readme', 'readmeUrl', 'reviewedAt', 'profileStatus', 'classificationBasis',
] as const satisfies readonly (keyof Project)[];

export function withLatestProfiles(data: Dataset, latest: Dataset): Dataset {
 const profiles = new Map(latest.projects.map(p=>[p.id,p]));
 return {...data, projects: data.projects.map(project=>{
  const profile = profiles.get(project.id);
  if (!profile || (project.editorial && !profile.editorial)) return project;
  const fields = Object.fromEntries(profileFields.map(key=>[key,profile[key]]));
  return {...project,...fields};
 })};
}
