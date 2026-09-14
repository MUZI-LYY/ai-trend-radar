export type Period = 'daily' | 'weekly' | 'monthly' | 'yearly' | 'all';
export interface Project {
 id: number; fullName: string; name: string; owner: string; avatar: string; url: string; homepage: string | null;
 stars: number; forks: number; language: string; license: string; topics: string[]; description: string;
 archived: boolean; stale?: boolean; createdAt: string; pushedAt: string; fetchedAt: string; firstSeen: string;
 category: string; related: string[]; kind: string; tags: string[]; ways: string[]; summary: string; overview: string;
 audience: string; features: string[]; usage: string; caveat: string; editorial: boolean; readme: string; readmeUrl: string;
 useCases?: string[]; gettingStarted?: string[]; requirements?: string[];
 reviewedAt?: string; classificationBasis: string; metrics: Record<Exclude<Period,'all'>, number | null>;
 historyStatus: string; history: {date: string; stars: number}[]; warnings: string[]; netSincePrevious: number | null; netBaselineAt: string | null;
}
export interface Dataset {
 viewType?: 'retrospective'; metadataDate?: string;
 schemaVersion: number; date: string; capturedAt: string; completedAt: string; periodEnd: string;
 periodStarts: Record<Exclude<Period,'all'>,string>; metric: string; source: string; timezoneNote: string;
 scope: string; status: string; warnings: string[]; failedRepositories: string[];
 categories: {id:string; label:string; description:string}[]; projects: Project[];
}
