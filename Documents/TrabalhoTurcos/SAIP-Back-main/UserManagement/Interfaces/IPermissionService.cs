using UserManagement.Entity;
using UserManagement.Model;

namespace UserManagement.Interfaces
{
    public interface IPermissionService
    {
        Task<Result<PagingResult<PagedList<Permission>>>> Paginate(PagingParameter pagingParameter);
        Task<Result<List<Permission>>> GetPermissions();
        Task<Result<Permission>> Save(Permission permission);
        Task<Result<Permission>> Update(Permission permission);
        Task<Result<Permission>> Delete(long id);
        Task<Result<Permission>> GetById(long id);

    }
}
