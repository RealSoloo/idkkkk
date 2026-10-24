"""Run the actual BABFT library with a rotated plot and a native-tool server double.
These tests verify local logic; they do not establish the live game's remote format.
"""
from pathlib import Path
import json
import unittest
from lupa import LuaRuntime

SOURCE = Path(__file__).resolve().parents[1].joinpath('Bab.txt').read_text()
BLOCK = SOURCE.split('-- BABFT BUILD LIBRARY BEGIN', 1)[1].split('-- BABFT BUILD LIBRARY END', 1)[0]
BLOCK = BLOCK.rstrip()[:-3] + '\nTest={validate=validate,safeName=safeName,placement=placement,partFrame=partFrame,onPlot=onPlot,state=state,nativeSpace=nativeSpace,placementArgs=placementArgs,preflight=preflight,clear=clearPreview}\nend'
FIXTURE = r'''
math.clamp=function(v,a,b) return math.max(a,math.min(b,v)) end
table.pack=table.pack or function(...) return {n=select('#',...),...} end
local V={};V.__index=V
Vector3={new=function(x,y,z) return setmetatable({X=x,Y=y,Z=z},V) end}
Color3={new=function(r,g,b) return {R=r,G=g,B=b} end,fromRGB=function(r,g,b) return {R=r/255,G=g/255,B=b/255} end}
local CF={};CF.__index=CF
CFrame={new=function(...)
 local a={...};if #a<12 then a={a[1] or 0,a[2] or 0,a[3] or 0,1,0,0,0,1,0,0,0,1} end
 return setmetatable({a=a},CF)
end}
function CF:GetComponents() return table.unpack(self.a) end
function CF:PointToWorldSpace(v)
 local a=self.a;return Vector3.new(a[1]+a[4]*v.X+a[5]*v.Y+a[6]*v.Z,a[2]+a[7]*v.X+a[8]*v.Y+a[9]*v.Z,a[3]+a[10]*v.X+a[11]*v.Y+a[12]*v.Z)
end
function CF:Inverse()
 local a=self.a;local b=CFrame.new(0,0,0,a[4],a[7],a[10],a[5],a[8],a[11],a[6],a[9],a[12])
 local p=b:PointToWorldSpace(Vector3.new(-a[1],-a[2],-a[3]));b.a[1]=p.X;b.a[2]=p.Y;b.a[3]=p.Z;return b
end
function CF:PointToObjectSpace(v) return self:Inverse():PointToWorldSpace(v) end
function CF:ToObjectSpace(b) return self:Inverse()*b end
function CF.__mul(a,b)
 local p=a:PointToWorldSpace(Vector3.new(b.a[1],b.a[2],b.a[3]));local c={p.X,p.Y,p.Z}
 for row=0,2 do for col=0,2 do local s=0;for k=0,2 do s=s+a.a[4+row*3+k]*b.a[4+k*3+col] end;c[4+row*3+col]=s end end
 return CFrame.new(table.unpack(c))
end
function CFrame.Angles(x,y,z) assert(x==0 and z==0);return CFrame.new(0,0,0,math.cos(y),0,math.sin(y),0,1,0,-math.sin(y),0,math.cos(y)) end
function typeof(v) return getmetatable(v)==CF and 'CFrame' or (type(v)=='table' and v.ClassName and 'Instance') or type(v) end
UDim2={new=function(...) return {...} end}
Enum={Material={Plastic={Name='Plastic'}},PartType={Block={Name='Block'},Ball={Name='Ball'},Cylinder={Name='Cylinder'}}}
function signal()
 local s={fns={}};function s:Connect(fn) table.insert(self.fns,fn) end;function s:Fire(...) for _,f in ipairs(self.fns) do f(...) end end;return s
end
nodes={}
local N={}
N.__index=function(self,k)
 if k=='Position' and rawget(self,'CFrame') then local a=self.CFrame.a;return Vector3.new(a[1],a[2],a[3]) end
 return N[k]
end
function node(name,kind,parent)
 local n=setmetatable({Name=name,ClassName=kind,Parent=parent,Size=Vector3.new(2,2,2),CFrame=CFrame.new(),Color=Color3.new(.5,.4,.3),Material=Enum.Material.Plastic,Shape=Enum.PartType.Block,Transparency=0,CanCollide=true},N)
 table.insert(nodes,n);return n
end
function N:IsA(k) return self.ClassName==k or k=='BasePart' and (self.ClassName=='Part' or self.ClassName=='WedgePart' or self.ClassName=='MeshPart') end
function N:GetAttributes() return self.attributes or {} end
function N:GetChildren() local out={} for _,n in ipairs(nodes) do if n.Parent==self then table.insert(out,n) end end return out end
function N:GetDescendants() local out={} for _,n in ipairs(self:GetChildren()) do table.insert(out,n);for _,c in ipairs(n:GetDescendants()) do table.insert(out,c) end end return out end
function N:FindFirstChild(name,recursive) for _,n in ipairs(recursive and self:GetDescendants() or self:GetChildren()) do if n.Name==name then return n end end end
function N:FindFirstChildWhichIsA(kind,recursive) for _,n in ipairs(recursive and self:GetDescendants() or self:GetChildren()) do if n:IsA(kind) then return n end end end
N.FindFirstChildOfClass=N.FindFirstChildWhichIsA
function N:FindFirstAncestorOfClass(kind) local n=self.Parent while n do if n:IsA(kind) then return n end;n=n.Parent end end
function N:IsDescendantOf(parent) local n=self.Parent while n do if n==parent then return true end;n=n.Parent end return false end
function N:Destroy() for _,n in ipairs(self:GetChildren()) do n:Destroy() end;self.Parent=nil;self.destroyed=true end
Instance={new=function(kind) return node(kind,kind) end}
Workspace=node('Workspace','Workspace');zone=node('GreenZone','Part',Workspace);zone.Size=Vector3.new(40,2,40);zone.CFrame=CFrame.new(100,5,50)*CFrame.Angles(0,math.pi/2,0)
referenceZone=node('WhiteZone','Part',Workspace);referenceZone.CFrame=CFrame.new(-53.565689086914062,-17.999992370605469,-345.5068664550781)
LocalPlayer=node('Me','Player');LocalPlayer.UserId=1;LocalPlayer.DisplayName='Me';LocalPlayer.Team={Name='Green'};LocalPlayer.Character=node('Character','Model',Workspace);LocalPlayer.CharacterRemoving=signal();teamSignal=signal()
function LocalPlayer:GetPropertyChangedSignal() return teamSignal end
backpack=node('Backpack','Backpack',LocalPlayer);tool=node('BuildingTool','Tool',backpack);remote=node('RF','RemoteFunction',tool);count=node('WoodBlock','IntValue',LocalPlayer);count.Value=30
function makeBlock(cf,kind) local m=node(kind or 'WoodBlock','Model',Workspace);local p=node('PPart','Part',m);p.CFrame=cf;return m,p end
original,primary=makeBlock(zone.CFrame*CFrame.new(3,2,0));original.attributes={OwnerUserId=1}
Players={list={LocalPlayer},PlayerAdded=signal(),PlayerRemoving=signal()}
function Players:GetPlayers() return self.list end
function Players:GetPlayerByUserId(id) for _,p in ipairs(self.list) do if p.UserId==id then return p end end end
Teams={GetTeams=function() return {LocalPlayer.Team} end}
Http={JSONEncode=function(_,v) return encode(v) end,JSONDecode=function(_,v) return decode(v) end}
game={GetService=function(_,name) if name=='HttpService' then return Http elseif name=='Players' then return Players elseif name=='Teams' then return Teams end end}
Hub={dir='SolosHub'};API={env={}};Panel={Sub=function() return {} end};T={Warn='warning',Text='text'};Live={Running=true};RunService={Heartbeat=signal()}
function getHum() return {Health=100} end
controls={};cleanups={};infos={}
function Section() return {} end
function InfoRow(_,text) local row={Text=text,Parent={}};table.insert(infos,row);return row end
function bind(s,f) s:Connect(f) end
function onUnload(f) table.insert(cleanups,f) end
function Button(_,name,_,cb) controls[name]={Fire=cb} end
function Input(_,name,_,_,cb) controls[name]={Fire=cb} end
function Toggle(_,name,initial,cb) local o={value=initial};function o.Set(v) o.value=v end;function o.Fire(v) o.value=v;cb(v) end;controls[name]=o;return o end
function Slider(_,name,_,_,initial,cb) local o={value=initial};function o.SetSilent(v) o.value=v end;function o.Fire(v) o.value=v;cb(v) end;controls[name]=o;return o end
function Dropdown(_,name,options,initial,cb) local o={options=options,i=initial};function o.SetOptions(opts) o.options=opts;o.i=1 end;function o.Set(i,silent) o.i=i;if cb and not silent then cb(i) end end;function o.Get() return o.i end;controls[name]=o;return o end
files={};folders={}
function isfolder(p) return folders[p] or false end
function makefolder(p) folders[p]=true end
function isfile(p) return files[p]~=nil end
function writefile(p,s) files[p]=s end
function readfile(p) assert(files[p],'missing file');return files[p] end
function listfiles(dir) local out={} for p in pairs(files) do if p:sub(1,#dir+1)==dir..'/' then table.insert(out,p) end end;return out end
queue={};ticks=0;os.clock=function() return ticks end
task={spawn=function(f) table.insert(queue,coroutine.create(f)) end,defer=function(f) table.insert(queue,coroutine.create(f)) end,wait=function() coroutine.yield() end}
function pump(n) for _=1,n or 30 do ticks=ticks+.3;local old=queue;queue={};for _,co in ipairs(old) do local ok,err=coroutine.resume(co);assert(ok,err);if coroutine.status(co)~='dead' then table.insert(queue,co) end end end end
sent=0
function native(self,kind,amount,plot,relative,flag,target,flag2,flag3)
 assert(self==remote and plot==zone and kind=='WoodBlock' and amount==count.Value and flag==true and flag2==false and flag3==true)
 local expected=zone.CFrame:ToObjectSpace(target)
 for i,x in ipairs({relative:GetComponents()}) do assert(math.abs(x-expected.a[i])<.00001) end
 sent=sent+1;count.Value=count.Value-1
 if reject then return false end
 local m,p=makeBlock(misplace and target*CFrame.new(3,0,0) or target,kind)
 return m,'native return'
end
function N:InvokeServer(...) return native(self,...) end

function capture() controls['Capture Player Build'].Fire() end
function preview() controls['Show Preview'].Fire(true) end
'''

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        def unpack(v):
            if hasattr(v, 'items'):
                pairs = list(v.items())
                if pairs and all(isinstance(k, int) for k, _ in pairs):
                    return [unpack(v[i]) for i in range(1, len(v)+1)]
                return {k: unpack(x) for k, x in pairs}
            return v
        self.lua.globals().encode = lambda v: json.dumps(unpack(v), allow_nan=False)
        self.lua.globals().decode = lambda v: self.lua.table_from(json.loads(v), recursive=True)
        self.lua.execute(FIXTURE + BLOCK)

    def test_local_save_load_and_no_overwrite_or_traversal(self):
        self.lua.execute('''assert(folders['SolosHub/Babft Builds']);capture()
        controls['Save as'].Fire('Boat one');local saved=files['SolosHub/Babft Builds/Boat one.json'];assert(saved)
        Test.state.data.blocks[1].kind='changed';controls['Save as'].Fire('Boat one');assert(files['SolosHub/Babft Builds/Boat one.json']==saved)
        controls['Save as'].Fire('../escape');assert(not files['SolosHub/escape.json'])
        controls['Load Selected Build'].Fire();assert(Test.state.data.blocks[1].kind=='WoodBlock')
        for _,s in ipairs({'..','a/b','a\\\\b','CON','lpt1','',string.rep('a',61)}) do assert(not Test.safeName(s)) end
        ''')

    def test_rotated_plot_transform_and_noncolliding_preview(self):
        self.lua.execute('''capture();preview();assert(#Test.state.ghosts==1)
        local g=Test.state.ghosts[1].object
        for i,x in ipairs({g.CFrame:GetComponents()}) do assert(math.abs(x-primary.CFrame.a[i])<.00001) end
        assert(g.Anchored and not g.CanCollide and not g.CanTouch and not g.CanQuery)
        controls['Exact offset'].Fire('5, 2, -4');controls['Rotation (degrees)'].Fire(90)
        local expected=Test.placement(zone,5,2,-4,90)*CFrame.new(3,1,0)
        for i,x in ipairs({g.CFrame:GetComponents()}) do assert(math.abs(x-expected.a[i])<.00001) end
        assert(primary.CFrame.a[1]==100 and primary.CFrame.a[2]==7 and primary.CFrame.a[3]==47)
        ''')

    def test_all_corners_bounds_and_invalid_offsets(self):
        self.lua.execute('''capture();preview();assert(Test.state.inside)
        controls['Exact offset'].Fire('17, 0, 0');assert(not Test.state.inside)
        controls['Exact offset'].Fire('0, -1, 0');assert(Test.state.x==17)
        controls['Exact offset'].Fire('nan, 0, 0');assert(Test.state.x==17)
        local cf=Test.placement(zone,19,2,0,45)
        assert(not Test.onPlot(zone,cf,Vector3.new(4,2,4)))
        ''')

    def test_corrupt_files_and_unsupported_geometry_preserve_current_build(self):
        self.lua.execute('''capture();local old=Test.state.data
        local p=old.blocks[1].parts[1];local cf=p.cf;p.cf={};assert(not Test.validate(old));p.cf=cf
        cf[4]=2;assert(not Test.validate(old));cf[4]=1
        p.size[1]=0/0;assert(not Test.validate(old));p.size[1]=2
        assert(Test.validate(old))
        local mesh=node('Mesh','DataModelMesh',primary);capture();assert(Test.state.data==old);mesh:Destroy()
        files['SolosHub/Babft Builds/Bad.json']='{"version":1,"format":"SolosHub.Babft","blocks":[]}'
        controls['Refresh Saved Builds'].Fire();controls['Load Selected Build'].Fire();assert(Test.state.data==old)
        ''')

    def test_native_build_without_learning_uses_preview_transform(self):
        self.lua.execute('''capture();preview()
        controls['Exact offset'].Fire('5, 1, 4');controls['Rotation (degrees)'].Fire(90)
        local want=Test.state.ghosts[1].object.CFrame;local before=sent
        controls['Build At Preview'].Fire();assert(Test.state.busy);pump()
        assert(not Test.state.busy and sent==before+1)
        local built=nodes[#nodes];for i,x in ipairs({built.CFrame:GetComponents()}) do assert(math.abs(x-want.a[i])<.00001) end
        local found=false;for _,row in ipairs(infos) do if row.Text:find('Finished | verified 1 / 1') then found=true end end;assert(found)
        ''')


    def test_wrong_server_placement_stops_without_retry(self):
        self.lua.execute('''capture();preview();misplace=true
        controls['Build At Preview'].Fire();pump(40)
        assert(sent==1 and not Test.state.busy)
        local found=false;for _,row in ipairs(infos) do if row.Text:find('Placement did not match') then found=true end end;assert(found)
        ''')

    def test_stop_freezes_controls_and_sends_no_further_blocks(self):
        self.lua.execute('''capture();local data=Test.state.data;table.insert(data.blocks,data.blocks[1]);preview()
        controls['Build At Preview'].Fire();pump(1);assert(sent==1)
        controls['Exact offset'].Fire('4,0,0');controls['Offset X (x0.1 studs)'].Fire(40);assert(Test.state.x==0)
        controls['Build At Preview'].Fire();controls['Capture Player Build'].Fire();assert(Test.state.data==data)
        controls['Stop Building'].Fire();pump();assert(sent==1 and not Test.state.busy)
        ''')

    def test_respawn_team_change_and_unload_clear_preview_and_stop_jobs(self):
        self.lua.execute('''capture();preview();local folder=Test.state.preview
        controls['Build At Preview'].Fire();LocalPlayer.CharacterRemoving:Fire();pump()
        assert(folder.destroyed and sent==0 and not Test.state.busy)
        preview();folder=Test.state.preview;teamSignal:Fire();assert(folder.destroyed)
        preview();folder=Test.state.preview;for _,fn in ipairs(cleanups) do fn() end;assert(folder.destroyed)
        local before=sent;remote:InvokeServer('WoodBlock',count.Value,zone,CFrame.new(0,2,0),true,zone.CFrame*CFrame.new(0,2,0),false,true);assert(sent==before+1)
        ''')






    def test_builder_rejection_never_retries(self):
        self.lua.execute('''capture();preview();reject=true
        controls['Build At Preview'].Fire();pump();assert(sent==1 and not Test.state.busy)
        local found=false;for _,row in ipairs(infos) do if row.Text:find('Game rejected') then found=true end end;assert(found)
        ''')

    def test_removed_plot_and_loaded_build_reset_preview_controls(self):
        self.lua.execute('''capture();controls['Save as'].Fire('A');preview()
        controls['Exact offset'].Fire('5, 1, 2');controls['Load Selected Build'].Fire()
        assert(Test.state.x==0 and Test.state.preview and controls['Offset X (x0.1 studs)'].value==0)
        preview();local folder=Test.state.preview;zone:Destroy();RunService.Heartbeat:Fire(.5)
        assert(folder.destroyed and not Test.state.preview)
        ''')

    def test_selected_player_filters_shared_plot_and_unknown_blocks(self):
        self.lua.execute('''local other=node('Other','Player');other.UserId=2;other.DisplayName='Me';other.Team=LocalPlayer.Team
        Players.list={LocalPlayer,other};controls['Refresh Players'].Fire()
        local b,p=makeBlock(zone.CFrame*CFrame.new(6,2,0));local tag=node('Tag','StringValue',b);tag.Value='Other'
        makeBlock(zone.CFrame*CFrame.new(9,2,0))
        controls['Source player'].Set(2);capture();assert(#Test.state.data.blocks==1 and Test.state.data.source.userId==2)
        controls['Source player'].Set(1);capture();assert(#Test.state.data.blocks==1 and Test.state.data.source.userId==1)
        ''')

    def test_player_folder_and_departure_preserve_selection(self):
        self.lua.execute('''local other=node('Other','Player');other.UserId=2;other.DisplayName='Other';other.Team=LocalPlayer.Team
        Players.list={LocalPlayer,other};controls['Refresh Players'].Fire()
        local folder=node('Other','Folder',Workspace);local b=makeBlock(zone.CFrame*CFrame.new(6,2,0));b.Parent=folder
        controls['Source player'].Set(2);capture();assert(Test.state.data.source.userId==2)
        local old=Test.state.data;Players.list={LocalPlayer};controls['Refresh Players'].Fire();capture();assert(Test.state.data==old)
        ''')

    def test_save_selects_new_file_and_load_shows_preview(self):
        self.lua.execute('''capture();controls['Save as'].Fire('Alpha');controls['Save as'].Fire('Zulu')
        assert(Test.state.files[controls['Saved builds'].Get()]=='Zulu')
        controls['Refresh Saved Builds'].Fire();assert(Test.state.files[controls['Saved builds'].Get()]=='Zulu')
        controls['Load Selected Build'].Fire();assert(Test.state.shown and #Test.state.ghosts==1 and sent==0)
        ''')

    def test_reported_motor_and_gold_frames_roundtrip(self):
        self.lua.execute('''assert(not controls['Learn Building Tool'] and not controls['Cancel Learning'])
        local samples={
          {'BoatMotor',1,CFrame.new(25,7.5,-47,-1,0,0,0,1,0,0,0,-1),CFrame.new(-28.565689086914062,-10.499992370605469,-392.5068664550781,-1,0,0,0,1,0,0,0,-1)},
          {'GoldBlock',540,CFrame.new(24,6.100000381469727,-49),CFrame.new(-29.565689086914062,-11.899991989135742,-394.5068664550781)}
        }
        for _,s in ipairs(samples) do
          local args=table.pack(Test.placementArgs(s[1],s[2],referenceZone,s[4],Test.nativeSpace()))
          assert(args.n==8 and args[1]==s[1] and args[2]==s[2] and args[3]==referenceZone and args[5] and args[7]==false and args[8])
          for i,x in ipairs({args[4]:GetComponents()}) do assert(math.abs(x-s[3].a[i])<.0001) end
          for i,x in ipairs({args[6]:GetComponents()}) do assert(math.abs(x-s[4].a[i])<.0001) end
        end
        ''')

    def test_unknown_coordinates_and_missing_inventory_send_nothing(self):
        self.lua.execute('''capture();preview();assert(pcall(Test.preflight))
        count.Value=0;assert(not pcall(Test.preflight));count.Value=30
        referenceZone.CFrame=CFrame.new(10,20,30)
        controls['Build At Preview'].Fire();pump();assert(sent==0 and not Test.state.busy)
        ''')

if __name__ == '__main__':
    unittest.main()
