// Centralized dialect display names.
// Add or update mappings here so UI components don't need edits when new dialects are added.
// Kept in sync with vocabulary schema v2 (docs/VOCABULARY_SCHEMA_V2.md):
// "bang-chu-cai" is the standalone alphabet group; regions display as "Miền ...".

const DIALECT_LABELS: Record<string, string> = {
  'common': 'Chung',
  'bang-chu-cai': 'Bảng chữ cái',
  'bac': 'Miền Bắc',
  'trung': 'Miền Trung',
  'nam': 'Miền Nam',
  'hoa-de': 'Hòa Đê',
  'can-tho': 'Cần Thơ',
  'spa': 'Spa',
  'ha-noi': 'Hà Nội',
  'saigon': 'Sài Gòn',

  // extend with any known dialect slugs
};

export default DIALECT_LABELS;
