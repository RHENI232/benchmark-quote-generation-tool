import { fetchClient } from './client';

export const regionApi = {
    getRegions: () => fetchClient('/api/regions'),
};
