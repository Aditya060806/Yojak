import api from '@/lib/api';

export type LabelTask = 'skills' | 'titles' | 'multilingual';

export interface Candidate {
    uri: string;
    label: string;
    score: number;
}

export interface SkillItem {
    tag: string;
    freq: string;
    method: string;
    score: string;
    example_titles: string;
    stratum: string;
    split: string;
    candidates: Candidate[];
    label: { gold_uri: string; labeller: string; labelled_at: string } | null;
}

export interface TitleItem {
    jobId: string;
    title: string;
    title_clean: string;
    companyName: string;
    tags_preview: string;
    occupation_label: string;
    stratum: string;
    candidates: Candidate[];
    label: { gold_uri: string; labeller: string; labelled_at: string } | null;
}

export interface PhraseItem {
    skill_uri: string;
    english_label: string;
    naukri_mentions: string;
    phrases: Record<string, string>;
}

export interface ItemsResponse<T> {
    task: LabelTask;
    key: string;
    items: T[];
    done: number;
    total: number;
    languages: Record<string, string> | null;
}

export interface LabelInput {
    key: string;
    gold_uri?: string;
    language?: string;
    phrase?: string;
    labeller: string;
}

export const labellingService = {
    items: async <T,>(task: LabelTask): Promise<ItemsResponse<T>> => {
        const r = await api.get<ItemsResponse<T>>(`/admin/labelling/${task}/items`);
        return r.data;
    },
    save: async (task: LabelTask, body: LabelInput) => {
        const r = await api.post(`/admin/labelling/${task}/labels`, body);
        return r.data;
    },
};
