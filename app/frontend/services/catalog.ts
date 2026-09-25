import api from '@/lib/api';
import type { AutocompleteOption } from '@/types';
import { isStaticMode, staticGet } from '@/lib/static';

let skillList: Promise<AutocompleteOption[]> | null = null;

/** Hosted-demo mode: search the ESCO skills that appear in the postings, client side. */
async function searchStaticSkills(q: string, limit: number): Promise<AutocompleteOption[]> {
    skillList ??= staticGet<AutocompleteOption[]>('skills.json');
    const needle = q.trim().toLowerCase();
    const all = await skillList;
    const starts = all.filter((s) => s.label.toLowerCase().startsWith(needle));
    const contains = all.filter((s) => !s.label.toLowerCase().startsWith(needle) && s.label.toLowerCase().includes(needle));
    return [...starts, ...contains].slice(0, limit);
}

export interface OccupationGroup {
    uri: string;
    code: string;
    label: string;
}

export interface SkillGroup {
    uri: string;
    label: string;
}

export interface ConceptScheme {
    uri: string;
    label: string;
    members: number;
}

export const catalogService = {
    searchSkills: async (q: string, limit = 10): Promise<AutocompleteOption[]> => {
        const response = await api.get<AutocompleteOption[]>('/catalog/skills', {
            params: { q, limit }
        });
        return response.data;
    },

    searchOccupations: async (q: string, limit = 10): Promise<AutocompleteOption[]> => {
        const response = await api.get<AutocompleteOption[]>('/catalog/occupations', {
            params: { q, limit }
        });
        return response.data;
    },

    /** Every ISCO occupation group (about 620), in one request. */
    getOccupationGroups: async (q?: string, limit = 100): Promise<OccupationGroup[]> => {
        const params = q ? { q, limit } : { all: true };
        const response = await api.get<OccupationGroup[]>('/catalog/occupation-groups', { params });
        return response.data;
    },

    getSkillGroups: async (q?: string, limit = 50): Promise<SkillGroup[]> => {
        const response = await api.get<SkillGroup[]>('/catalog/skill-groups', {
            params: { q, limit }
        });
        return response.data;
    },

    getConceptSchemes: async (): Promise<ConceptScheme[]> => {
        const response = await api.get<ConceptScheme[]>('/catalog/concept-schemes');
        return response.data;
    }
};
