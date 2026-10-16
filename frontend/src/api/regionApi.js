import { fetchClient } from './client';

export const regionApi = {
    getRegions: () => fetchClient('/api/regions'),
    updateRegionFxRate: (regionId, payload) => fetchClient(`/api/regions/${regionId}/fx-rate`, {
        method: 'PUT',
        body: payload,
    }),
};
