using Microsoft.EntityFrameworkCore;
using System.Data;
using UserManagement.DbContexts;
using UserManagement.Entity;
using UserManagement.Interfaces;
using UserManagement.Model;

namespace UserManagement.Services
{
    public class RoleService : IRoleService
    {
        private readonly UserManagementContext _dbContext;

        public RoleService(UserManagementContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<Result<PagingResult<PagedList<Role>>>> Paginate(PagingParameter pagingParameter)
        {
            var result = new Result<PagingResult<PagedList<Role>>>();

            string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.Roles.Where(x=> (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText)))).Select(s => new Role()
                    {
                        Id = s.Id,
                        Name = s.Name,
                        IsDeleted = s.IsDeleted,
                        IsSystemData = s.IsSystemData,
                        Permissions = _dbContext.RolePermissions.Where(x => !x.IsDeleted && x.RoleId == s.Id).Select(p => p.PermissionId).ToList()
                    });

                    var pagination = PagedList<Role>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);

                    result.SetData(new PagingResult<PagedList<Role>>()
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
        public async Task<Result<List<Role>>> GetRoles()
        {
            var result = new Result<List<Role>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                var data = await _dbContext.Roles.Where(x => !x.IsDeleted).ToListAsync();

                result.SetData(data);
                result.SetMessage("İşlem başarı ile gerçekleşti.");
            }
            
            return result;
        }

        public async Task<Result<Role>> Save(Role role)
        {
            var result = new Result<Role>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    if (!_dbContext.Roles.Where(x => x.Name == role.Name && !x.IsDeleted).Any())
                    {
                        _dbContext.Add(role);
                        await _dbContext.SaveChangesAsync();

                        foreach (var permission in role.Permissions)
                        {
                            RolePermission rp = new RolePermission();
                            rp.RoleId = role.Id;
                            rp.PermissionId = permission;
                            rp.IsDeleted = false;

                            _dbContext.Add(rp);
                            await _dbContext.SaveChangesAsync();
                        }

                        transaction.Commit();

                        result.SetData(role);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Aynı isim ile tanımlı bir rol bulunmaktadır.");
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

        public async Task<Result<Role>> Update(Role role)
        {
            var result = new Result<Role>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldRole = await _dbContext.Roles.Where(x => x.Id == role.Id && !x.IsDeleted).FirstOrDefaultAsync();

                    if (oldRole != null)
                    {
                        if (!_dbContext.Roles.Where(x => x.Id != oldRole.Id && x.Name == oldRole.Name && !x.IsDeleted).Any())
                        {
                            oldRole.Name = role.Name;

                            var rolePerms = await _dbContext.RolePermissions.Where(x => x.RoleId == role.Id).ToListAsync();
                            _dbContext.RolePermissions.RemoveRange(rolePerms);

                            var users = await _dbContext.UserRoles.Include(x => x.User).Where(x => x.RoleId == role.Id).Select(s => s.User.Id).ToListAsync();
                            var userPerms = await _dbContext.UserPermissions.Where(x => users.Contains(x.UserId)).ToListAsync();
                            _dbContext.UserPermissions.RemoveRange(userPerms);

                            await _dbContext.SaveChangesAsync();

                            foreach (var permission in role.Permissions)
                            {
                                RolePermission rp = new RolePermission();
                                rp.RoleId = role.Id;
                                rp.PermissionId = permission;
                                rp.IsDeleted = false;

                                _dbContext.Add(rp);
                                await _dbContext.SaveChangesAsync();

                                foreach(var user in users)
                                {
                                    UserPermission up = new UserPermission();
                                    up.UserId = user;
                                    up.PermissionId = permission;
                                    up.IsDeleted = false;

                                    _dbContext.Add(up);
                                    await _dbContext.SaveChangesAsync();

                                }
                            }

                            transaction.Commit();

                            result.SetData(role);
                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage("Aynı isim ile tanımlı bir rol bulunmaktadır.");
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

        public async Task<Result<Role>> Delete(long id)
        {
            var result = new Result<Role>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldRole = await _dbContext.Roles.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldRole != null)
                    {
                        oldRole.IsDeleted = true;

                        var userRole = await _dbContext.UserRoles.Where(x => x.RoleId == oldRole.Id).FirstOrDefaultAsync();
                        _dbContext.UserRoles.RemoveRange(userRole);

                        var rolePermissions = await _dbContext.RolePermissions.Where(x => x.RoleId == oldRole.Id).ToListAsync();
                        _dbContext.RolePermissions.RemoveRange(rolePermissions);

                        var permissions = rolePermissions.Select(s => s.PermissionId).ToList();
                        var userPermissions = await _dbContext.UserPermissions.Where(x => permissions.Contains(x.PermissionId)).ToListAsync();
                        _dbContext.UserPermissions.RemoveRange(userPermissions);


                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldRole);
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

        public async Task<Result<Role>> GetById(long id)
        {
            var result = new Result<Role>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var role = await _dbContext.Roles.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (role != null)
                    {   
                        role.Permissions = await _dbContext.RolePermissions.Where(x => x.RoleId == id).Select(s => s.PermissionId).ToListAsync();

                        result.SetData(role);
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
    }
}
