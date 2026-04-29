import UserManagementSection from '../../features/admin/components/UserManagementSection';
import ProjectListSection from '../../features/admin/components/ProjectListSection';

export default function SuperAdminPage() {
  return (
    <div className="grid grid-cols-2 gap-[32px] w-full h-[calc(100vh-12rem)] min-h-[600px]">
      {/* Left Column: User Management */}
      <UserManagementSection />

      {/* Right Column: Project List */}
      <ProjectListSection />
    </div>
  );
}
