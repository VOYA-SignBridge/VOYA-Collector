import re
from pathlib import Path

def main():
    p = Path("frontend/src/pages/LabelsPage.tsx")
    content = p.read_text(encoding="utf-8")

    # Replace groupedSessions table logic with an individual samples table
    old_table_section = r'''            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm text-left text-gray-500">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                  <tr>
                    <th scope="col" className="px-4 py-3 w-10 text-center">
                      <input 
                        type="checkbox" 
                        className="rounded border-gray-300"
                        checked={
                          \(\(\) => \{
                            const filteredGroups = groupedSessions.filter\(g => \{
                              if \(!samplesSearch\) return true;
                              const q = samplesSearch.toLowerCase\(\);
                              return \(g.user \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                                     \(g.filePrefix \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                                     \(g.session_id \|\| ''\).toLowerCase\(\).includes\(q\);
                            \}\);
                            return filteredGroups.length > 0 && selectedSessions.size === filteredGroups.length;
                          \}\)\(\)
                        }
                        onChange=\{\(e\) => \{
                          if \(e.target.checked\) \{
                            const filteredIds = groupedSessions
                              .filter\(g => \{
                                if \(!samplesSearch\) return true;
                                const q = samplesSearch.toLowerCase\(\);
                                return \(g.user \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                                       \(g.filePrefix \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                                       \(g.session_id \|\| ''\).toLowerCase\(\).includes\(q\);
                              \}\)
                              .map\(g => g.group_id\);
                            setSelectedSessions\(new Set\(filteredIds\)\);
                          \} else \{
                            setSelectedSessions\(new Set\(\)\);
                          \}
                        \}\}
                      />
                    </th>
                    <th scope="col" className="px-4 py-3 w-1/4">Người thu thập</th>
                    <th scope="col" className="px-4 py-3">Session</th>
                    <th scope="col" className="px-4 py-3 text-center">Số lượng</th>
                    <th scope="col" className="px-4 py-3">Ngày tạo</th>
                    <th scope="col" className="px-4 py-3 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  \{\(\(\) => \{
                    const filteredGroups = groupedSessions.filter\(g => \{
                      if \(!samplesSearch\) return true;
                      const q = samplesSearch.toLowerCase\(\);
                      return \(g.user \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                             \(g.filePrefix \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                             \(g.session_id \|\| ''\).toLowerCase\(\).includes\(q\);
                    \}\);
                    
                    if \(filteredGroups.length === 0\) \{
                      return \(
                        <tr>
                          <td colSpan=\{6\} className="px-4 py-8 text-center text-gray-500">
                            Chưa có cụm sample nào phù hợp.
                          </td>
                        </tr>
                      \);
                    \}
                    
                    return filteredGroups
                      .slice\(\(samplesPage - 1\) \* SAMPLES_PER_PAGE, samplesPage \* SAMPLES_PER_PAGE\)
                      .map\(\(group\) => \(
                      <tr key=\{group.group_id\} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 text-center">
                          <input 
                            type="checkbox" 
                            className="rounded border-gray-300"
                            checked=\{selectedSessions.has\(group.group_id\)\}
                            onChange=\{\(e\) => \{
                              const next = new Set\(selectedSessions\);
                              if \(e.target.checked\) next.add\(group.group_id\);
                              else next.delete\(group.group_id\);
                              setSelectedSessions\(next\);
                            \}\}
                          />
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-900 break-all">
                          \{editSessionTarget === group.group_id \? \(
                            <input 
                              type="text" 
                              className="input input-sm w-full"
                              value=\{editSessionUserId\}
                              onChange=\{e => setEditSessionUserId\(e.target.value\)\}
                              disabled=\{editSessionSaving\}
                              placeholder="Tên người thu thập"
                              autoFocus
                            />
                          \) : \(
                            group.user \|\| '-'
                          \)\}
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-xs font-mono text-gray-600 truncate max-w-\[150px\]" title=\{group.session_id\}>
                            \{group.session_id \|\| '-'\}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-gray-700">
                          \{group.samples.length\} mẫu
                        </td>
                        <td className="px-4 py-3 text-xs whitespace-nowrap">
                          \{group.created_at \? new Date\(group.created_at\).toLocaleString\('vi-VN'\) : '-'\}
                        </td>
                        <td className="px-4 py-3 text-right">
                          \{editSessionTarget === group.group_id \? \(
                            <div className="flex justify-end gap-2">
                              <Button variant="ghost" size="sm" onClick=\{\(\) => setEditSessionTarget\(null\)\} disabled=\{editSessionSaving\}>Hủy</Button>
                              <Button variant="primary" size="sm" onClick=\{handleSaveSession\} loading=\{editSessionSaving\}>Lưu</Button>
                            </div>
                          \) : \(
                            <div className="flex justify-end gap-2">
                              <Button 
                                variant="secondary" 
                                size="sm" 
                                onClick=\{\(\) => \{
                                  setEditSessionTarget\(group.group_id\);
                                  setEditSessionUserId\(group.user \|\| ''\);
                                \}\}
                              >
                                Sửa
                              </Button>
                              <Button 
                                variant="danger" 
                                size="sm" 
                                disabled=\{deleteSessionSaving\}
                                onClick=\{\(\) => \{
                                  if \(confirm\(`Bạn có chắc chắn muốn đưa toàn bộ $\{group.samples.length\} mẫu trong cụm này vào thùng rác không\?`\)\) \{
                                    handleDeleteSessions\(\[group.group_id\]\);
                                  \}
                                \}\}
                              >
                                Xóa
                              </Button>
                            </div>
                          \)\}
                        </td>
                      </tr>
                    \)\);
                  \}\)\(\)\}
                </tbody>
              </table>
            </div>'''
            
    new_table_section = '''            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm text-left text-gray-500">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                  <tr>
                    <th scope="col" className="px-4 py-3">File / Sample</th>
                    <th scope="col" className="px-4 py-3">Người thu thập</th>
                    <th scope="col" className="px-4 py-3">Session</th>
                    <th scope="col" className="px-4 py-3">Ngày tạo</th>
                    <th scope="col" className="px-4 py-3 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const filteredSamples = samplesList.filter(s => {
                      if (!samplesSearch) return true;
                      const q = samplesSearch.toLowerCase();
                      return (s.user || '').toLowerCase().includes(q) ||
                             (s.file || '').toLowerCase().includes(q) ||
                             (s.session_uid || '').toLowerCase().includes(q);
                    });
                    
                    if (filteredSamples.length === 0) {
                      return (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                            Chưa có sample nào.
                          </td>
                        </tr>
                      );
                    }
                    
                    return filteredSamples
                      .slice((samplesPage - 1) * SAMPLES_PER_PAGE, samplesPage * SAMPLES_PER_PAGE)
                      .map((sample) => (
                      <tr key={sample.sample_id || sample.file || Math.random()} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900 break-all">
                          {sample.file || sample.sample_id || '-'}
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-900 break-all">
                          {editSessionTarget === sample.session_uid ? (
                            <input 
                              type="text" 
                              className="input input-sm w-full"
                              value={editSessionUserId}
                              onChange={e => setEditSessionUserId(e.target.value)}
                              disabled={editSessionSaving}
                              placeholder="Tên người thu thập"
                              autoFocus
                            />
                          ) : (
                            sample.user || '-'
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-xs font-mono text-gray-600 truncate max-w-[150px]" title={sample.session_uid}>
                            {sample.session_uid || '-'}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs whitespace-nowrap">
                          {sample.created_at ? new Date(sample.created_at).toLocaleString('vi-VN') : '-'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {editSessionTarget === sample.session_uid ? (
                            <div className="flex justify-end gap-2">
                              <Button variant="ghost" size="sm" onClick={() => setEditSessionTarget(null)} disabled={editSessionSaving}>Hủy</Button>
                              <Button variant="primary" size="sm" onClick={handleSaveSession} loading={editSessionSaving}>Lưu</Button>
                            </div>
                          ) : (
                            <div className="flex justify-end gap-2">
                              <Button 
                                variant="secondary" 
                                size="sm" 
                                onClick={() => {
                                  setEditSessionTarget(sample.session_uid);
                                  setEditSessionUserId(sample.user || '');
                                }}
                              >
                                Sửa Người Dùng
                              </Button>
                              <Button 
                                variant="danger" 
                                size="sm" 
                                disabled={deleteSessionSaving}
                                onClick={() => {
                                  if (confirm(`Bạn có chắc chắn muốn xóa mẫu này không?`)) {
                                    handleDeleteSessions([sample.session_uid]);
                                  }
                                }}
                              >
                                Xóa
                              </Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>'''
            
    pagination_old = r'''            \{\(\(\) => \{
              const filteredGroups = groupedSessions.filter\(g => \{
                if \(!samplesSearch\) return true;
                const q = samplesSearch.toLowerCase\(\);
                return \(g.user \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                       \(g.filePrefix \|\| ''\).toLowerCase\(\).includes\(q\) \|\|
                       \(g.session_id \|\| ''\).toLowerCase\(\).includes\(q\);
              \}\);
              const totalFiltered = filteredGroups.length;
              if \(totalFiltered > SAMPLES_PER_PAGE\) \{
                return \(
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between mt-4">
                    <span className="text-sm text-gray-700 mb-2 sm:mb-0">
                      Hiển thị <span className="font-semibold">\{\(samplesPage - 1\) \* SAMPLES_PER_PAGE \+ 1\}</span> đến <span className="font-semibold">\{Math.min\(samplesPage \* SAMPLES_PER_PAGE, totalFiltered\)\}</span> trong số <span className="font-semibold">\{totalFiltered\}</span> cụm
                    </span>
                    <Pagination 
                      currentPage=\{samplesPage\} 
                      totalPages=\{Math.ceil\(totalFiltered / SAMPLES_PER_PAGE\)\} 
                      onPageChange=\{setSamplesPage\} 
                    />
                  </div>
                \);
              \}
              return null;
            \}\)\(\)\}'''

    pagination_new = '''            {(() => {
              const filteredSamples = samplesList.filter(s => {
                if (!samplesSearch) return true;
                const q = samplesSearch.toLowerCase();
                return (s.user || '').toLowerCase().includes(q) ||
                       (s.file || '').toLowerCase().includes(q) ||
                       (s.session_uid || '').toLowerCase().includes(q);
              });
              const totalFiltered = filteredSamples.length;
              if (totalFiltered > SAMPLES_PER_PAGE) {
                return (
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between mt-4">
                    <span className="text-sm text-gray-700 mb-2 sm:mb-0">
                      Hiển thị <span className="font-semibold">{(samplesPage - 1) * SAMPLES_PER_PAGE + 1}</span> đến <span className="font-semibold">{Math.min(samplesPage * SAMPLES_PER_PAGE, totalFiltered)}</span> trong số <span className="font-semibold">{totalFiltered}</span> mẫu
                    </span>
                    <Pagination 
                      currentPage={samplesPage} 
                      totalPages={Math.ceil(totalFiltered / SAMPLES_PER_PAGE)} 
                      onPageChange={setSamplesPage} 
                    />
                  </div>
                );
              }
              return null;
            })()}'''
            
    header_buttons_old = r'''              \{selectedSessions.size > 0 && \(
                <Button 
                  variant="danger" 
                  onClick=\{\(\) => \{
                    if \(confirm\(`Bạn có chắc chắn muốn đưa $\{selectedSessions.size\} cụm đã chọn vào thùng rác không\?`\)\) \{
                      handleDeleteSessions\(Array.from\(selectedSessions\)\);
                    \}
                  \}\}
                  loading=\{deleteSessionSaving\}
                >
                  Xóa \{selectedSessions.size\} cụm đã chọn
                </Button>
              \)\}'''

    header_buttons_new = '''              {/* removed bulk delete since individual view doesn't use checkboxes currently */}'''
            
    if re.search(old_table_section, content):
        content = re.sub(old_table_section, new_table_section, content)
    else:
        print("Failed to find old table section.")

    if re.search(pagination_old, content):
        content = re.sub(pagination_old, pagination_new, content)
    else:
        print("Failed to find pagination section.")
        
    if re.search(header_buttons_old, content):
        content = re.sub(header_buttons_old, header_buttons_new, content)
    else:
        print("Failed to find header buttons.")

    p.write_text(content, encoding="utf-8")
    print("Done")

if __name__ == "__main__":
    main()
