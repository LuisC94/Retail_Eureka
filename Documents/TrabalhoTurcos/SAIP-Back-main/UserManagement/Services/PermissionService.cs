using Microsoft.EntityFrameworkCore;
using System.Data;
using UserManagement.DbContexts;
using UserManagement.Entity;
using UserManagement.Interfaces;
using UserManagement.Model;

namespace UserManagement.Services
{
    public class PermissionService : IPermissionService
    { 
        private readonly UserManagementContext _dbContext;

        public PermissionService(UserManagementContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<Result<PagingResult<PagedList<Permission>>>> Paginate(PagingParameter pagingParameter)
        {
            var result = new Result<PagingResult<PagedList<Permission>>>();

            string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.Permissions.Where(x => (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText))));
                    var pagination = PagedList<Permission>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);

                    result.SetData(new PagingResult<PagedList<Permission>> ()
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

        public async Task<Result<List<Permission>>> GetPermissions()
        {
            var result = new Result<List<Permission>>();
            
            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Permissions.Where(x => !x.IsDeleted).ToListAsync();

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

        public async Task<Result<Permission>> Save(Permission permission)
        {
            var result = new Result<Permission>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    if (!_dbContext.Permissions.Where(x => (x.Name == permission.Name || x.Code == permission.Code) && !x.IsDeleted).Any())
                    {
                        _dbContext.Add(permission);
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(permission);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Aynı isim veya kodla tanımlı bir yetki bulunmaktadır.");
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

        public async Task<Result<Permission>> Update(Permission permission)
        {
            var result = new Result<Permission>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldPermission = await _dbContext.Permissions.Where(x => x.Id == permission.Id && !x.IsDeleted).FirstOrDefaultAsync();

                    if (oldPermission != null)
                    {
                        if (!_dbContext.Permissions.Where(x => x.Id != oldPermission.Id && (x.Name == permission.Name || x.Code == permission.Code) && !x.IsDeleted).Any())
                        {
                            oldPermission.Name = permission.Name;
                            oldPermission.Code = permission.Code;

                            await _dbContext.SaveChangesAsync();
                            transaction.Commit();

                            result.SetData(permission);
                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage("Aynı isim veya kodla tanımlı bir yetki bulunmaktadır.");
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

        public async Task<Result<Permission>> Delete(long id)
        {
            var result = new Result<Permission>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldPermission = await _dbContext.Permissions.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldPermission != null)
                    {
                        oldPermission.IsDeleted = true;

                        var rolePermissions = await _dbContext.RolePermissions.Where(x => x.PermissionId == oldPermission.Id).ToListAsync();
                        _dbContext.RolePermissions.RemoveRange(rolePermissions);


                        var userPermissions = await _dbContext.UserPermissions.Where(x => x.PermissionId == oldPermission.Id).ToListAsync();
                        _dbContext.UserPermissions.RemoveRange(userPermissions);

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldPermission);
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

        public async Task<Result<Permission>> GetById(long id)
        {
            var result = new Result<Permission>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var permission = await _dbContext.Permissions.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (permission != null)
                    {
                        result.SetData(permission);
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
