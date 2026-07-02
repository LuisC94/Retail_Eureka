using UserManagement.Entity;
using UserManagement.Model;

namespace UserManagement.Interfaces
{
    public interface IRoleService
    {
        Task<Result<PagingResult<PagedList<Role>>>> Paginate(PagingParameter pagingParameter);
        Task<Result<List<Role>>> GetRoles();
        Task<Result<Role>> Save(Role role);
        Task<Result<Role>> Update(Role role);
        Task<Result<Role>> Delete(long id);
        Task<Result<Role>> GetById(long id);

    }
}
