using UserManagement.Entity;
using UserManagement.Model;

namespace UserManagement.Interfaces
{
    public interface IOrganizationService
    {
        Task<Result<PagingResult<PagedList<Organization>>>> Paginate(PagingParameter pagingParameter);
        Task<Result<List<Organization>>> GetOrganizations();
        Task<Result<Organization>> Save(Organization organization);
        Task<Result<Organization>> Update(Organization organization);
        Task<Result<Organization>> Delete(long id);
        Task<Result<Organization>> GetById(long id);

    }
}
