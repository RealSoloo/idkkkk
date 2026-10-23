"""Test the actual shared hub loader with executor/network/compiler doubles."""
from pathlib import Path
import unittest
from lupa import LuaRuntime

SOURCE = Path(__file__).resolve().parents[1].joinpath('Soloshub.txt').read_text()
LOADER = SOURCE[SOURCE.index('\tfunction Hub.loadGameModule(g)'):SOURCE.index('\n\t-- ------------------------------------------------------------ game list')]
URLS = SOURCE[SOURCE.index('\tHub.ModuleURLs = {'):SOURCE.index('\n\n\t-- everything a game script')]

class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''Hub={path=function(name) return "SolosHub/"..name end};S={};T={};C={};warn=function(s) lastWarning=s end
        requestCalls=0;httpCalls=0;compiled=0;initialized=0
        request=function(options) requestCalls=requestCalls+1;lastURL=options.Url;return {StatusCode=200,Body='valid module'} end
        game={HttpGet=function(self,url,noCache) httpCalls=httpCalls+1;lastURL=url;return 'fallback module' end}
        loadstring=function(source,name)
          compiled=compiled+1;lastSource=source;lastChunk=name
          return function(h,s,t,c) assert(h==Hub and s==S and t==T and c==C);initialized=initialized+1 end
        end
        ''')
        self.lua.execute(URLS+LOADER)

    def test_all_six_games_use_own_urls_and_hub_api(self):
        self.lua.execute('''for _,id in ipairs({'mm2','arsenal','pf','lt2','doomspire','bab'}) do
          assert(Hub.loadGameModule({id=id,name=id}))
          assert(lastURL==Hub.ModuleURLs[id]);assert(lastChunk=='='..id)
        end
        assert(requestCalls==6 and httpCalls==0 and initialized==6)
        ''')

    def test_http_error_uses_httpget_fallback(self):
        self.lua.execute('''request=function() error('HTTP 403') end
        assert(Hub.loadGameModule({id='lt2',name='Lumber Tycoon 2'}))
        assert(httpCalls==1 and initialized==1 and lastSource=='fallback module')
        assert(Hub.LastModuleError==nil)
        ''')

    def test_bad_responses_and_missing_request_fall_back(self):
        self.lua.execute('''for _,response in ipairs({{},'not a table',{StatusCode=404,Body='not found'},{StatusCode=200,Body='  '},{Success=false,Body='denied'}}) do
          request=function() return response end
          assert(Hub.loadGameModule({id='mm2'}))
        end
        request=nil;assert(Hub.loadGameModule({id='mm2'}))
        assert(httpCalls==6)
        ''')

    def test_both_methods_fail_preserves_actual_error(self):
        self.lua.execute('''request=function() error('HTTP 403') end
        game.HttpGet=function() error('HttpGet blocked') end
        local ok,err=Hub.loadGameModule({id='mm2',name='Murder Mystery 2'})
        assert(not ok and string.find(err,'HTTP 403') and string.find(err,'HttpGet blocked'))
        assert(Hub.LastModuleError.id=='mm2' and Hub.LastModuleError.message==err)
        assert(compiled==0 and initialized==0)
        ''')

    def test_bundled_modules_load_with_network_disabled(self):
        self.lua.execute('''Hub.BundledModules={mm2='included mm2',lt2='included lt2'}
        request=function() error('network must not be called') end
        game.HttpGet=function() error('network must not be called') end
        assert(Hub.loadGameModule({id='mm2'}));assert(lastSource=='included mm2')
        assert(Hub.loadGameModule({id='lt2'}));assert(lastSource=='included lt2')
        assert(initialized==2)
        ''')

    def test_local_file_fallback_after_network_failure(self):
        self.lua.execute('''request=function() return {StatusCode=404} end
        game.HttpGet=function() return '' end
        canFile=true;isfile=function(path) return path=='SolosHub/mod_lt2.lua' end
        readfile=function() return 'local file contents' end
        assert(Hub.loadGameModule({id='lt2'}));assert(lastSource=='local file contents')
        ''')

    def test_compile_and_initialization_failures_are_distinguished(self):
        self.lua.execute('''loadstring=function() return nil,'syntax problem' end
        local ok,err=Hub.loadGameModule({id='pf'});assert(not ok and string.find(err,'compile failed'))
        loadstring=function() error('compiler threw') end
        ok,err=Hub.loadGameModule({id='pf'});assert(not ok and string.find(err,'compiler threw'))
        loadstring=function() return function() error('game API missing') end end
        ok,err=Hub.loadGameModule({id='pf'});assert(not ok and string.find(err,'module initialization failed'))
        ''')

class StandaloneTests(unittest.TestCase):
    def test_bundle_contains_current_sources_and_loads_all_six_offline(self):
        import importlib.util
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('build_standalone',root/'scripts/build_standalone.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        generated=root.joinpath('SoloshubStandalone.txt').read_text()
        self.assertEqual(generated,builder.build())
        start=generated.index('\tHub.BundledModules = {')
        end=generated.index('\t-- everything a game script can use',start)
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute("Hub={};S={};T={};C={};warn=function() end;networkCalls=0;initialized=0")
        lua.execute(URLS+generated[start:end]+LOADER)
        for key,file in builder.MODULES.items():
            self.assertEqual(lua.globals().Hub.BundledModules[key],root.joinpath(file).read_text())
        lua.execute('''request=function() networkCalls=networkCalls+1;error('blocked') end
        game={HttpGet=function() networkCalls=networkCalls+1;error('blocked') end}
        loadstring=function(source,name)
          assert(source==Hub.BundledModules[string.sub(name,2)])
          return function(h,s,t,c) assert(h==Hub and s==S and t==T and c==C);initialized=initialized+1 end
        end
        for _,id in ipairs({'mm2','arsenal','pf','lt2','doomspire','bab'}) do assert(Hub.loadGameModule({id=id})) end
        assert(networkCalls==0 and initialized==6)
        ''')

if __name__=='__main__': unittest.main()
