import api from '@/lib/api';
import type { AutocompleteOption } from '@/types';

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
