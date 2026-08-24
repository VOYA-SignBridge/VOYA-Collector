/**
 * Các trang LÀM VIỆC của một tổ chức: `/org/:tenantId/upload`, `/labels`, …
 *
 * Vì sao chúng là trang RIÊNG mà vẫn dùng chung phần thân
 * --------------------------------------------------------
 * Tổ chức có route riêng, vỏ riêng, tiêu đề riêng — nên đây là những trang
 * riêng theo mọi nghĩa người dùng nhìn thấy: địa chỉ chia sẻ được, thanh bên
 * của tổ chức, và một dải nhắc rõ dữ liệu đang chảy về đâu.
 *
 * Phần THÂN thì dùng lại thành phần đã có, và đó là chủ ý. Chép đôi màn hình
 * thu dữ liệu sẽ tạo ra hai bản phải sửa mọi lỗi hai lần, và hai bản ấy sẽ trôi
 * khỏi nhau — bản Cộng đồng được dùng hằng ngày nên được sửa, bản tổ chức thì
 * không. Cái người dùng cần là "trang của tổ chức tôi", không phải "một bản sao
 * mã nguồn thứ hai".
 *
 * Đích đóng góp KHÔNG do trang này quyết
 * ---------------------------------------
 * Nó do `users.active_tenant_id` ở máy chủ quyết, và đã được đặt lúc bấm "Vào"
 * ở trang chọn tổ chức. Nghĩa là cùng một thành phần, khi vẽ dưới `/org/<id>`,
 * thật sự đang ghi vào tổ chức ấy — không phải một lời hứa của giao diện.
 *
 * Dải nhắc bên dưới vì thế là MÔ TẢ chứ không phải điều khiển: nó nói lại điều
 * máy chủ đã quyết, để người dùng không phải nhớ mình đang đứng ở đâu.
 */

import type { ReactNode } from "react";
import { lazy, Suspense } from "react";
import { useParams } from "react-router-dom";

import LoadingScreen from "../../components/LoadingScreen";
import { useI18n } from "../../i18n";
import { BuildingIcon } from "../../components/ui/Icons";

const UploadPage = lazy(() => import("../UploadPage"));
const LabelsPage = lazy(() => import("../LabelsPage"));
const CollectionSessionsPage = lazy(() => import("../CollectionSessionsPage"));
const RealtimeRecognitionPage = lazy(() => import("../RealtimeRecognitionPage"));
const TrainingPipeline = lazy(() => import("../training/TrainingPipeline"));

function DaiNhac({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { tenantId = "" } = useParams<{ tenantId: string }>();

  return (
    <div>
      <div className="mb-4 flex items-start gap-2 rounded-lg bg-ctu-blue/5 px-3 py-2 text-sm text-slate-700">
        <BuildingIcon className="mt-0.5 h-4 w-4 shrink-0 text-ctu-blue" aria-hidden="true" />
        <p>
          {t("Bạn đang làm việc trong tổ chức {ma}. Dữ liệu tạo ở đây thuộc về tổ chức đó, không vào Cộng đồng.", {
            ma: tenantId,
          })}
        </p>
      </div>
      <Suspense fallback={<LoadingScreen />}>{children}</Suspense>
    </div>
  );
}

export function OrgUploadPage() {
  return <DaiNhac><UploadPage /></DaiNhac>;
}

export function OrgLabelsPage() {
  return <DaiNhac><LabelsPage /></DaiNhac>;
}

export function OrgSessionsPage() {
  return <DaiNhac><CollectionSessionsPage /></DaiNhac>;
}

export function OrgRealtimePage() {
  return <DaiNhac><RealtimeRecognitionPage /></DaiNhac>;
}

export function OrgTrainingPage() {
  return <DaiNhac><TrainingPipeline /></DaiNhac>;
}
