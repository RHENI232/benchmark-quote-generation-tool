import { fetchClient } from './client';

export const solutionApi = {
    getSolutions: () => fetchClient('/api/solutions'),
};
