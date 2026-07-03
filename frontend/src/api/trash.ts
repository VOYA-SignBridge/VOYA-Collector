import axiosClient from './axiosClient';

export interface TrashClass {
  class_uid: string;
  class_idx: number;
  slug: string;
  label_original: string;
  language: string;
  dialect: string;
  folder_name: string;
  created_at: string;
  deleted_at: string;
}

export interface TrashSample {
  sample_uid: string;
  class_uid: string;
  slug: string;
  label_original: string;
  user_id: string;
  status: string;
  error_log: string;
  created_at: string;
  deleted_at: string;
}

export const trashApi = {
  getTrashedClasses: async (): Promise<TrashClass[]> => {
    const res = await axiosClient.get('/api/v1/trash/classes');
    return res.data?.data || [];
  },
  getTrashedSamples: async (): Promise<TrashSample[]> => {
    const res = await axiosClient.get('/api/v1/trash/samples');
    return res.data?.data || [];
  },
  restoreClass: async (classUid: string) => {
    const res = await axiosClient.post(`/api/v1/trash/classes/${classUid}/restore`);
    return res.data;
  },
  restoreSample: async (sampleUid: string) => {
    const res = await axiosClient.post(`/api/v1/trash/samples/${sampleUid}/restore`);
    return res.data;
  },
  hardDeleteClass: async (classUid: string) => {
    const res = await axiosClient.delete(`/api/v1/trash/classes/${classUid}/hard`);
    return res.data;
  },
  hardDeleteSample: async (sampleUid: string) => {
    const res = await axiosClient.delete(`/api/v1/trash/samples/${sampleUid}/hard`);
    return res.data;
  }
};
