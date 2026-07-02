using Microsoft.EntityFrameworkCore;
using System.Data;
using UserManagement.DbContexts;
using UserManagement.Entity;
using UserManagement.Interfaces;
using UserManagement.Model;

namespace UserManagement.Services
{
    public class OrganizationService : IOrganizationService
    {
        private readonly UserManagementContext _dbContext;

        public OrganizationService(UserManagementContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<Result<PagingResult<PagedList<Organization>>>> Paginate(PagingParameter pagingParameter)
        {
            var result = new Result<PagingResult<PagedList<Organization>>>();

            string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.Organizations.Where(x=> (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText))));
                    var pagination = PagedList<Organization>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);

                    result.SetData(new PagingResult<PagedList<Organization>>()
                    {
                        Items = pagination,
                        TotalCount = pagination.TotalCount,
                    });

                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<List<Organization>>> GetOrganizations()
        {
            var result = new Result<List<Organization>>();
            
            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Organizations.Include(x => x.ParentOrganization).Where(x => !x.IsDeleted).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<Organization>> Save(Organization organization)
        {
            var result = new Result<Organization>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    if (!_dbContext.Organizations.Where(x => (x.Name == organization.Name) && !x.IsDeleted).Any())
                    {
                        _dbContext.Add(organization);
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(organization);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Aynı isim ile tanımlı bir organizasyon bulunmaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<Organization>> Update(Organization organization)
        {
            var result = new Result<Organization>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldOrganization = await _dbContext.Organizations.Where(x => x.Id == organization.Id && !x.IsDeleted).FirstOrDefaultAsync();

                    if (oldOrganization != null)
                    {
                        if (!_dbContext.Organizations.Where(x => x.Id != oldOrganization.Id && x.Name == organization.Name && !x.IsDeleted).Any())
                        {
                            oldOrganization.Name = organization.Name;
                            oldOrganization.ParentId = organization.ParentId;

                            await _dbContext.SaveChangesAsync();
                            transaction.Commit();

                            result.SetData(organization);
                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage("Aynı isim ile tanımlı bir organizasyon bulunmaktadır.");
                        }
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<Organization>> Delete(long id)
        {
            var result = new Result<Organization>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldOrganization = await _dbContext.Organizations.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldOrganization != null)
                    {
                        oldOrganization.IsDeleted = true;

                        var users = await _dbContext.OrganizationUsers.Where(x => x.OrganizationId == oldOrganization.Id).ToListAsync();

                        foreach (var user in users)
                        {
                            user.IsDeleted = true;
                        }
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldOrganization);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<Organization>> GetById(long id)
        {
            var result = new Result<Organization>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var Organization = await _dbContext.Organizations.Include(x => x.ParentOrganization).Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (Organization != null)
                    {
                        result.SetData(Organization);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();
                }
            }

            return result;
        }
    }
}
