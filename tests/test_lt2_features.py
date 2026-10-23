"""LT2 regression checks with a small fake Roblox world, never a live executor.

Run: python -m pip install lupa && python tests/test_lt2_features.py
"""
from pathlib import Path
from lupa import LuaRuntime

SOURCE = (Path(__file__).resolve().parents[1] / 'Lt2.txt').read_text()

FIXTURE = r'''
local Vec={}
Vec.__index=function(v,k)
 if k=='Magnitude' then return math.sqrt(v.X^2+v.Y^2+v.Z^2) end
 if k=='Unit' then return v/v.Magnitude end
end
function vector(x,y,z) return setmetatable({X=x,Y=y,Z=z},Vec) end
function Vec.__add(a,b) return vector(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
function Vec.__sub(a,b) return vector(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
function Vec.__mul(a,b)
 if type(b)=='number' then return vector(a.X*b,a.Y*b,a.Z*b) end
 return vector(a.X*b.X,a.Y*b.Y,a.Z*b.Z)
end
function Vec.__div(a,b) return vector(a.X/b,a.Y/b,a.Z/b) end
Vector3={new=vector,zero=vector(0,0,0)}
local CF={}; CF.__index=CF
function cf(x,y,z)
 local p=type(x)=='table' and x or vector(x or 0,y or 0,z or 0)
 return setmetatable({Position=p,LookVector=vector(0,0,-1),UpVector=vector(0,1,0)},CF)
end
function CF.__mul(a,b) return cf(a.Position+b.Position) end
function CF.__add(a,b) return cf(a.Position+b) end
function CF:Inverse() return cf(self.Position*-1) end
CFrame={new=cf,lookAt=function(p) return cf(p) end}
function signal()
 local s={listeners={}}
 function s:Connect(fn)
  local item={fn=fn,on=true}; table.insert(self.listeners,item)
  return {Disconnect=function() item.on=false end}
 end
 function s:Fire(...) for _,item in ipairs(self.listeners) do if item.on then item.fn(...) end end end
 return s
end
local methods={}; local Meta={}
Meta.__index=function(o,k)
 if methods[k] then return methods[k] end
 if o.props[k]~=nil then return o.props[k] end
 for _,c in ipairs(o.children) do if c.Parent==o and c.Name==k then return c end end
end
Meta.__newindex=function(o,k,v)
 local old=o.props[k]; o.props[k]=v
 if k=='Parent' and v and v~=old then table.insert(v.children,o) end
 if k=='CFrame' then o.props.Position=v.Position end
 if old~=v and o.signals[k] then o.signals[k]:Fire() end
end
function node(name,kind,parent,props)
 local n=setmetatable({props={Name=name,ClassName=kind},children={},signals={}},Meta)
 for k,v in pairs(props or {}) do n[k]=v end
 n.Parent=parent; return n
end
function methods:IsA(c) return self.ClassName==c or c=='BasePart' and self.ClassName=='Part' end
function methods:GetChildren()
 local out={} for _,c in ipairs(self.children) do if c.Parent==self then table.insert(out,c) end end return out
end
function methods:GetDescendants()
 local out={}; local function visit(o) for _,c in ipairs(o:GetChildren()) do table.insert(out,c);visit(c) end end
 visit(self);return out
end
function methods:FindFirstChild(name,deep)
 for _,c in ipairs(deep and self:GetDescendants() or self:GetChildren()) do if c.Name==name then return c end end
end
function methods:FindFirstChildWhichIsA(kind,deep)
 for _,c in ipairs(deep and self:GetDescendants() or self:GetChildren()) do if c:IsA(kind) then return c end end
end
methods.FindFirstChildOfClass=methods.FindFirstChildWhichIsA
function methods:GetPropertyChangedSignal(k) self.signals[k]=self.signals[k] or signal();return self.signals[k] end
function methods:GetPivot() return self.Main.CFrame end
function methods:GetExtentsSize() return self.Main.Size end
function methods:PivotTo(goal) self.Main.CFrame=goal;if onPivot then onPivot(self,goal) end end
function methods:Destroy() self.Parent=nil end
function methods:IsDescendantOf(ancestor)
 local n=self.Parent;while n do if n==ancestor then return true end;n=n.Parent end;return false
end
Workspace=node('Workspace','Workspace'); models=node('PlayerModels','Folder',Workspace)
LocalPlayer=node('Me','Player'); backpack=node('Backpack','Backpack',LocalPlayer)
character=node('Character','Model',Workspace)
root=node('HumanoidRootPart','Part',character,{CFrame=cf(0,0,0),Size=vector(2,2,1)})
function getRoot() return root end
function getChar() return character end
function getHum() return {Health=100} end
function ownedModel(name,class,owner,length,pos)
 local m=node(name,'Model',models)
 local o=node('Owner','Folder',m);node('OwnerString','StringValue',o,{Value=owner or 'Me'})
 node('LastInteraction','NumberValue',o,{Value=0})
 node('Main','Part',m,{CFrame=cf(pos or vector(0,0,0)),Size=vector(1,length or 1,1),Anchored=false})
 if class then node('TreeClass','StringValue',m,{Value=class}) end
 return m
end
function blueprint()
 local m=ownedModel('Wall',nil,'Me',1,vector(20,0,0));node('Type','StringValue',m,{Value='Blueprint'});return m
end
Live={Running=true,Unlocked=true,BindingActive=false};LT={token=0,busy=false}
LTExtra={pickers={},stopHooks={}}; notices={}; callbacks={}; controls={}; cleanup={}
T={Warn=1,Bad=2,Good=3,Sub=4,Accent=5}
function notify(text) table.insert(notices,text) end
function onUnload(fn) table.insert(cleanup,fn) end
function addCleanup(fn) table.insert(cleanup,fn) end
local queue={}; now=0; os.clock=function() return now end
function advance(dt) now=now+(dt or .1);if onWait then onWait() end end
task={wait=advance,spawn=function(fn) table.insert(queue,fn) end,delay=function() end}
function drain() local n=0;while #queue>0 do n=n+1;assert(n<100,'unexpected task loop');table.remove(queue,1)() end end
RemoteProxy={};DragRemote={}
function DragRemote:FireServer(m) m.Owner.LastInteraction.Value=m.Owner.LastInteraction.Value+1 end
function Section() return {} end
function Collapse() return {} end
function InfoRow(_,text) return {Text=text} end
function Button(_,text,_,fn) callbacks[text]=fn end
function Toggle(_,text,default,cb)
 local v=default;local obj={}
 function obj.Set(x) v=x end
 function obj.Get() return v end
 function obj.Fire(x) v=x;if cb then cb(x) end end
 controls[text]=obj;return obj
end
function Slider(_,text,_,_,default,cb)
 local v=default;local o={Get=function() return v end,Set=function(x) v=x;if cb then cb(x) end end}
 controls[text]=o;return o
end
function Dropdown(_,text,options,default,cb)
 local opts,v=options,default;local o={}
 function o.SetOptions(x) opts=x;v=1 end
 function o.Set(x,silent) v=x;if cb and not silent then cb(x,opts[x]) end end
 function o.Get() return v end
 function o.Name() return opts[v] end
 controls[text]=o;return o
end
function bind(s,fn) s:Connect(fn) end
UIS={InputBegan=signal(),InputChanged=signal(),InputEnded=signal()}
function UIS:GetFocusedTextBox() return nil end
function UIS:GetMouseLocation() return cursor end
Enum={UserInputType={MouseButton1=1,MouseMovement=2}}
mouse={}; PlotTab={};ToolsTab={};Sl={};SlOpt={}
UDim2={fromOffset=function(x,y) return {X=x,Y=y} end}
EspGui=node('Esp','ScreenGui')
function new(kind,props,parent) return node(props.Name or kind,kind,parent,props) end
API={cam=function() return {WorldToScreenPoint=function(_,p) return {X=p.X,Y=p.Z,Z=1},true end} end}
'''

def setup():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('assert(load(...))', SOURCE)
    lua.execute(FIXTURE)
    for first, last in [
        ('local function classOf(', 'local function sectionsOf('),
        ('local function ownedByMe(', 'local function myLogs('),
        ('local function mainPartOf(', 'local function topModel('),
        ('local function topModel(', 'local function myPlot('),
        ('local function claimDrag(', 'local function moveLog('),
    ]:
        lua.execute(SOURCE[SOURCE.index(first):SOURCE.index(last)].replace('local function ', 'function ', 1))
    lua.execute(SOURCE[SOURCE.index('-- Shared helpers for'):SOURCE.index('-- ---------------------------------------------------- WOOD: get trees')])
    lua.execute(SOURCE[SOURCE.index('local function setStatus('):SOURCE.index('local function waitRespawn(')].replace('local function ', 'function '))
    return lua


def test_layout_and_ownership():
    lua = setup()
    lua.execute(r'''
    local grid=LTExtra.layout(8,2,2,2,false); assert(#grid==8)
    local seen={};local sumX,sumZ=0,0
    for _,p in ipairs(grid) do local key=p.X..','..p.Y..','..p.Z;assert(not seen[key]);seen[key]=true;sumX=sumX+p.X;sumZ=sumZ+p.Z end
    assert(sumX==0 and sumZ==0)
    local pyramid=LTExtra.layout(14,3,3,3,true);assert(#pyramid==14 and pyramid[14].Y==2)
    assert(LTExtra.layout(15,3,3,3,true)==nil)
    assert(#LTExtra.layout(0,1,1,1,false)==0)
    local oak=ownedModel('Plank','Oak','Me',4)
    ownedModel('Plank','Oak','Other',4);ownedModel('Plank','Birch','Me',4);ownedModel('Plank','Oak','Me',8)
    assert(#LTExtra.scanPlanks('Oak',3,5)==1)
    assert(#LTExtra.scanPlanks(nil,5,3)==0)
    local same=ownedModel('Plank','Oak','Me',4.02)
    assert(LTExtra.sameSelectionKind(oak,same,true))
    same.Main.Size=vector(1,8,1);assert(not LTExtra.sameSelectionKind(oak,same,true))
    assert(LTExtra.sameSelectionKind(oak,same,false))
    assert(not LTExtra.moveOwned(ownedModel('Plank','Oak','Other',4),cf(30,0,0),function()return true end))
    local before=oak.Main.CFrame
    assert(not LTExtra.moveOwned(oak,cf(30,0,0),function()return false end));assert(oak.Main.CFrame==before)
    onWait=function() LT.token=LT.token+1 end
    local token=LT.token
    assert(not LTExtra.moveOwned(oak,cf(30,0,0),function()return LT.token==token end))
    assert(oak.Main.CFrame==before);onWait=nil
    root.CFrame=cf(0,0,0);LTExtra.withReturn(function()root.CFrame=cf(99,0,0)end);assert(root.Position.X==0)
    LTExtra.withReturn(function()LT.token=LT.token+2;root.CFrame=cf(88,0,0)end);assert(root.Position.X==88)
    ''')
    print('PASS: grid/pyramid capacity and centering; owner/class/length filters; cancellation; return-position isolation')


def test_blueprint_jobs():
    lua = setup()
    first = SOURCE.index('-- ---------------------------------------------------- PLOT: plank selection and blueprint filling')
    last = SOURCE.index('-- ---------------------------------------------------- VEHICLE\n', first)
    lua.execute(SOURCE[first:last])
    lua.execute(r'''
    local bp=blueprint();local a=ownedModel('Plank','Oak','Me',2);local b=ownedModel('Plank','Oak','Me',3)
    ownedModel('Plank','Oak','Other',1)
    local deliveries=0
    onPivot=function(m)
      if m.Name=='Plank' then deliveries=deliveries+1;m.Parent=nil;if deliveries==2 then bp.Parent=nil end end
    end
    callbacks['Refresh Owned Planks']()
    callbacks['Fill All My Blueprints']();drain()
    assert(deliveries==2 and not LT.busy and root.Position.X==0)
    assert(notices[#notices]:find('Confirmed deliveries: 2',1,true))
    local enemy=ownedModel('Wall',nil,'Other');node('Type','StringValue',enemy,{Value='Blueprint'})
    onPivot=function()error('must not move anything for unowned blueprint')end
    callbacks['Fill All My Blueprints']();drain();assert(notices[#notices]=='No owned blueprints found')
    local stalled=blueprint();local plank=ownedModel('Plank','Oak','Me',2);onPivot=nil
    callbacks['Fill All My Blueprints']();drain()
    local found=false;for _,text in ipairs(notices)do if text:find('No fill progress confirmed',1,true) then found=true end end
    assert(found and not LT.busy and root.Position.X==0)
    controls['Click To Fill Blueprint'].Fire(true)
    callbacks['Stop Blueprint Job']();assert(not controls['Click To Fill Blueprint'].Get())
    ''')
    print('PASS: actual blueprint fill callbacks consume owned planks; reject unowned blueprints; report no-progress; stop click mode')


def test_lasso():
    lua = setup()
    # Run the actual lasso block against the same selection list API it receives.
    lua.execute('selected={}; function setSel(m,on) selected[m]=on or nil end;function updSel()end')
    first = SOURCE.index('-- Rectangle selection uses')
    last = SOURCE.index('Toggle(Sl, "Group Selection', first)
    lua.execute(SOURCE[first:last])
    lua.execute(r'''
    local a=ownedModel('Plank','Oak','Me',2,vector(20,0,20))
    local other=ownedModel('Plank','Oak','Other',2,vector(20,0,20))
    local outside=ownedModel('Plank','Oak','Me',2,vector(100,0,100))
    controls['Lasso Selection'].Fire(true)
    cursor={X=0,Y=0};UIS.InputBegan:Fire({UserInputType=1},true)
    cursor={X=40,Y=40};UIS.InputEnded:Fire({UserInputType=1});assert(next(selected)==nil)
    cursor={X=0,Y=0};UIS.InputBegan:Fire({UserInputType=1},false)
    cursor={X=40,Y=40};UIS.InputChanged:Fire({UserInputType=2});UIS.InputEnded:Fire({UserInputType=1})
    assert(selected[a] and not selected[other] and not selected[outside])
    stopAll();assert(not controls['Lasso Selection'].Get())
    ''')
    print('PASS: actual lasso input callbacks; processed-input guard; owned objects only; rectangle bounds; Stop resets mode')


def shop_setup():
    lua = setup()
    lua.execute(r'''
    ShopTab={};SH={all={}};STORES={{'Store'}};money=10000;buys=0;opens=0
    store=node('ShopItems','Folder',Workspace)
    playerBlueprints=node('PlayerBlueprints','Folder',LocalPlayer);unlocked=node('Blueprints','Folder',playerBlueprints)
    Interaction=node('Interaction','Folder');interactionEvent=node('ClientInteracted','RemoteEvent',Interaction)
    function scanAllItems() end
    function shopItemsFor() return store end
    function fetchFunds() return money end
    function commas(n) return tostring(n) end
    function axeNameOf(t) return t.ToolTip and t.ToolTip.Value end
    function stock(key)
      local b=node('Box','Model',store);node('BoxItemName','StringValue',b,{Value=key})
      node('Main','Part',b,{CFrame=cf(20,0,0),Size=vector(1,1,1),Anchored=false})
      return b
    end
    function buyBox(_,box,alive)
      if not alive() then return false end
      buys=buys+1;money=money-20
      local key=box.BoxItemName.Value;box.Parent=nil
      local purchased=ownedModel('Box Purchased by Me',nil,'Me',1)
      node('PurchasedBoxItemName','StringValue',purchased,{Value=key})
      root.CFrame=cf(200,0,0)
      if onBuy then onBuy() end
      return true
    end
    function interactionEvent:FireServer(model,action)
      if action=='Open box' then
       opens=opens+1;local key=model.PurchasedBoxItemName.Value;model.Parent=nil
       if key=='Wall2' then node(key,'BoolValue',unlocked,{Value=true})
       else local item=ownedModel('Item',nil,'Me',1);node('ItemName','StringValue',item,{Value=key}) end
      elseif action=='Pick up tool' then
       local tool=node('Tool','Tool',backpack);node('ToolTip','StringValue',tool,{Value='Rukiryaxe'});model.Parent=nil
      end
    end
    ''')
    catalog_start = SOURCE.index('local BLUEPRINT_KEYS =')
    catalog_end = SOURCE.index('local STORES =', catalog_start)
    first = SOURCE.index('-- Additional purchases use')
    last = SOURCE.index('\nend\n\n-- ---------------------------------------------------- TOOLS:', first)
    lua.execute(SOURCE[catalog_start:catalog_end] + SOURCE[first:last])
    return lua


def test_purchases():
    lua = shop_setup()
    lua.execute(r'''
    SH.all={{key='Wall2',name='Wall',price=20,store=1}}
    stock('Wall2')
    function selectWall() for i=1,69 do controls.Blueprint.Set(i,true);if controls.Blueprint.Name():find('Wall2 ($20)',1,true) then return end end end
    callbacks['Refresh Blueprint Catalog']()
    for i=1,69 do controls.Blueprint.Set(i,true);if controls.Blueprint.Name()=='Wall2 ($20)' then break end end
    selectWall();callbacks['Purchase Selected Blueprint']();drain()
    assert(unlocked:FindFirstChild('Wall2') and buys==1 and opens==1 and root.Position.X==0)
    selectWall();callbacks['Purchase Selected Blueprint']();drain();assert(buys==1)
    unlocked.Wall2.Parent=nil
    money=0;selectWall();callbacks['Purchase Selected Blueprint']();drain();assert(buys==1)
    money=100;selectWall();callbacks['Purchase Selected Blueprint']();drain();assert(buys==1) -- no stock
    stock('Wall2');onBuy=stopAll
    selectWall();callbacks['Purchase Selected Blueprint']();drain();assert(buys==2 and opens==1 and not LT.busy and root.Position.X==0)
    ''')
    # Use the real purchase-ownership predicate against another player's model.
    start = SOURCE.index('local function inMine(')
    end = SOURCE.index('local function itemState(', start)
    lua.execute(SOURCE[start:end] + r'''
    local mine=ownedModel('Box',nil,'Me',1);local theirs=ownedModel('Box',nil,'Other',1)
    assert(inMine(mine.Main) and not inMine(theirs.Main))
    ''')
    print('PASS: purchase callbacks skip owned blueprints; reject insufficient funds/out-of-stock; cancel before opening; verify actual item owner')


def test_quest():
    lua = shop_setup()
    lua.execute(r'''
    SH.all={{key='CanOfWorms',name='Worms',price=20,store=1},{key='BagOfSand',name='Sand',price=20,store=1},{key='LightBulb',name='Bulb',price=20,store=1}}
    stock('CanOfWorms');stock('BagOfSand');stock('LightBulb')
    local delivered={}
    onPivot=function(m)
      if m.ItemName then delivered[m.ItemName.Value]=m.Main.Position end
      if delivered.CanOfWorms and delivered.BagOfSand and delivered.LightBulb and not rewardSpawned then
       rewardSpawned=true;local reward=ownedModel('Model',nil,'',1,vector(320,45,1919))
       node('ToolName','StringValue',reward,{Value='Rukiryaxe'})
      end
    end
    callbacks['Complete Rukiryaxe Quest']();drain()
    assert(buys==3 and opens==3 and rewardSpawned and #backpack:GetChildren()==1 and root.Position.X==0)
    assert(delivered.CanOfWorms.X==317.3 and delivered.BagOfSand.X==319.5 and delivered.LightBulb.X==322.4)
    assert(notices[#notices]=='Rukiryaxe pickup confirmed' and not LT.busy)
    ''')
    lua = shop_setup()
    lua.execute(r'''
    SH.all={{key='CanOfWorms',name='Worms',price=20,store=1}}
    stock('CanOfWorms');onBuy=stopAll
    callbacks['Complete Rukiryaxe Quest']();drain()
    assert(buys==1 and opens==0 and #backpack:GetChildren()==0 and root.Position.X==0 and not LT.busy)
    ''')
    print('PASS: quest purchases/opens/delivers all three materials; confirms new reward pickup; cancellation leaves later materials untouched')


def test_module_initialization():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(FIXTURE)
    lua.execute(r'''
    local function enums(t)
      return setmetatable(t or {},{__index=function(self,k)local v={Name=k};rawset(self,k,v);return v end})
    end
    setmetatable(Enum,{__index=function(self,k)local v=enums();rawset(self,k,v);return v end})
    Color3={new=vector,fromRGB=vector};BrickColor={new=function()return {Color=vector(1,1,1)}end}
    UDim2.new=function(...)return {...}end;UDim2.fromScale=UDim2.new;UDim={new=UDim2.new}
    math.clamp=function(x,a,b)return math.max(a,math.min(x,b))end
    Instance={new=function(kind,parent)return node(kind,kind,parent)end}
    task.defer=task.spawn
    game={PlaceId=13822889,DescendantAdded=signal()}
    local storage=node('ReplicatedStorage','ReplicatedStorage');local lighting=node('Lighting','Lighting')
    local interaction=node('Interaction','Folder',storage);node('RemoteProxy','RemoteEvent',interaction);node('ClientIsDragging','RemoteEvent',interaction)
    function game:GetService(name)
      if name=='ReplicatedStorage' then return storage end
      if name=='Lighting' then return lighting end
      if name=='Workspace' then return Workspace end
    end
    function LocalPlayer:GetMouse()return mouse end
    LocalPlayer.CharacterAdded=signal()
    Players=node('Players','Players');Players.PlayerAdded=signal();Players.PlayerRemoving=signal()
    function Players:GetPlayers()return {LocalPlayer}end
    RunService={Heartbeat=signal(),RenderStepped=signal(),Stepped=signal()}
    UIS.InputEnded=signal();UIS.InputChanged=signal()
    Hub={API={},GamePanel=function()return {Sub=function(name)table.insert(pages,name);return node(name,'Frame')end}end,gameHeader=function()end}
    pages={}
    local api=Hub.API
    api.Live=Live;api.LocalPlayer=LocalPlayer;api.Players=Players;api.Workspace=Workspace;api.RunService=RunService;api.UIS=UIS
    api.Section=function()return node('Section','Frame')end;api.Collapse=api.Section
    api.Dropdown=Dropdown;api.Toggle=Toggle;api.Slider=Slider;api.Button=Button;api.InfoRow=InfoRow
    api.Input=function()return node('Input','TextBox',nil,{Text=''})end;api.Keybind=function()end
    api.TabButtons={['Lumber Tycoon 2']={Btn={}}};api.Tabs={Teleports=node('Teleports','Frame')}
    api.EspGui=EspGui;api.new=new;api.bind=bind;api.round=function()end;api.notify=notify;api.onUnload=onUnload
    api.filterTabs=function()end;api.getRoot=getRoot;api.getChar=getChar;api.getHum=getHum;api.cam=API.cam
    ''')
    lua.execute('local fn=assert(load(...));fn(Hub,{}, {},{})', SOURCE)
    lua.execute(r'''
    assert(#pages==8,'Existing eight game pages must remain unchanged')
    assert(callbacks['Fill All My Blueprints'] and callbacks['Complete Rukiryaxe Quest'] and callbacks['Purchase All Missing Blueprints'])
    assert(controls['Lasso Selection'] and controls['Pyramid Sorter'] and controls['Match Plank Length In Groups'])
    assert(not controls['Lasso Selection'].Get() and not controls['Click To Fill Blueprint'].Get())
    ''')
    print('PASS: full module initialization; all eight existing tabs retained; new controls registered without starting actions')


if __name__ == '__main__':
    test_layout_and_ownership()
    test_blueprint_jobs()
    test_lasso()
    test_purchases()
    test_quest()
    test_module_initialization()
