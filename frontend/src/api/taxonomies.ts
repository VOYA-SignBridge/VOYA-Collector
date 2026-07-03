import axiosClient from './axiosClient';

export interface Language {
  code: string;
  name: string;
}

export interface Dialect {
  code: string;
  language_code: string;
  name: string;
}

export const taxonomiesApi = {
  getLanguages: async (): Promise<Language[]> => {
    const res = await axiosClient.get('/api/v1/taxonomies/languages');
    return res.data?.data || [];
  },
  getDialects: async (language_code?: string): Promise<Dialect[]> => {
    const params = language_code ? { language_code } : undefined;
    const res = await axiosClient.get('/api/v1/taxonomies/dialects', { params });
    return res.data?.data || [];
  },
  createDialect: async (code: string, name: string, language_code: string = 'vn'): Promise<Dialect> => {
    const res = await axiosClient.post('/api/v1/taxonomies/dialects', { code, name, language_code });
    return res.data?.data;
  }
};
