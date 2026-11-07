package com.mirror;

import android.content.pm.ApplicationInfo;
import android.content.res.AssetManager;
import android.content.res.Configuration;
import android.content.res.Resources;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.os.IBinder;
import android.util.Base64;
import android.util.DisplayMetrics;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

/**
 * Prints each app's label and launcher icon (PNG, base64) so Mirror can show
 * them in its Apps list. Runs on the phone through app_process, the way
 * scrcpy's server runs:
 *
 *   CLASSPATH=/data/local/tmp/mirror-helper.dex app_process / com.mirror.IconDump SIZE PKG...
 *
 * Output, one line per package:  pkg \t label \t base64-png   (or pkg \t ! \t error)
 *
 * Read-only. It asks the package service for the app's ApplicationInfo (as the
 * shell user, like `pm`), opens the app's APK resources and draws its icon. No
 * app Context is borrowed (the shell user may not impersonate one).
 */
public final class IconDump {
    private static final int DPI = 480; // xxhdpi: crisp after scaling down

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, false, "UTF-8");
        if (args.length < 2) {
            out.println("usage: IconDump SIZE PKG...");
            out.flush();
            return;
        }
        int size = Math.max(16, Math.min(192, Integer.parseInt(args[0])));

        Class<?> sm = Class.forName("android.os.ServiceManager");
        IBinder binder = (IBinder) sm.getMethod("getService", String.class).invoke(null, "package");
        Object ipm = Class.forName("android.content.pm.IPackageManager$Stub")
                .getMethod("asInterface", IBinder.class).invoke(null, binder);
        Method getAppInfo = null;
        for (Method m : ipm.getClass().getMethods()) {
            if (m.getName().equals("getApplicationInfo") && m.getParameterTypes().length == 3) {
                getAppInfo = m; // (String, int|long flags, int userId)
                break;
            }
        }
        if (getAppInfo == null) {
            throw new IllegalStateException("IPackageManager.getApplicationInfo not found");
        }
        boolean longFlags = getAppInfo.getParameterTypes()[1] == long.class;

        Constructor<AssetManager> amCtor = AssetManager.class.getDeclaredConstructor();
        amCtor.setAccessible(true);
        Method addAssetPath = AssetManager.class.getMethod("addAssetPath", String.class);
        DisplayMetrics dm = new DisplayMetrics();
        dm.setToDefaults();
        dm.densityDpi = DPI;
        dm.density = DPI / 160f;
        Configuration cfg = new Configuration();
        cfg.setToDefaults();
        cfg.densityDpi = DPI;

        for (int i = 1; i < args.length; i++) {
            String pkg = args[i];
            try {
                ApplicationInfo ai = (ApplicationInfo) getAppInfo.invoke(ipm, pkg, longFlags ? (Object) 0L : (Object) 0, 0);
                if (ai == null) {
                    out.println(pkg + "\t!\tnot installed");
                    out.flush();
                    continue;
                }
                AssetManager am = amCtor.newInstance();
                addAssetPath.invoke(am, ai.sourceDir);
                if (ai.splitSourceDirs != null) {
                    for (String split : ai.splitSourceDirs) {
                        addAssetPath.invoke(am, split);
                    }
                }
                Resources res = new Resources(am, dm, cfg);
                String label = pkg;
                if (ai.nonLocalizedLabel != null) {
                    label = ai.nonLocalizedLabel.toString();
                } else if (ai.labelRes != 0) {
                    try {
                        label = res.getText(ai.labelRes).toString();
                    } catch (Throwable ignore) {
                        // keep the package name
                    }
                }
                label = label.replace('\t', ' ').replace('\n', ' ');
                Drawable d = null;
                if (ai.icon != 0) {
                    try {
                        d = res.getDrawableForDensity(ai.icon, DPI, null);
                    } catch (Throwable ignore) {
                        d = null;
                    }
                }
                if (d == null) {
                    d = Resources.getSystem().getDrawable(android.R.drawable.sym_def_app_icon, null);
                }
                Bitmap b = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
                Canvas c = new Canvas(b);
                d.setBounds(0, 0, size, size);
                d.draw(c);
                ByteArrayOutputStream png = new ByteArrayOutputStream();
                b.compress(Bitmap.CompressFormat.PNG, 100, png);
                b.recycle();
                am.close();
                out.println(pkg + "\t" + label + "\t" + Base64.encodeToString(png.toByteArray(), Base64.NO_WRAP));
            } catch (Throwable t) {
                Throwable cause = t.getCause() != null ? t.getCause() : t;
                out.println(pkg + "\t!\t" + cause.getClass().getSimpleName());
            }
            out.flush();
        }
    }
}
