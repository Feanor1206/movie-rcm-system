package com.dippie.moviercm.service.storage;

import com.dippie.moviercm.exception.MediaUnavailableException;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.ClosedChannelException;
import java.nio.channels.FileChannel;
import java.nio.channels.NonWritableChannelException;
import java.nio.channels.SeekableByteChannel;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * SeekableByteChannel wrapper for Google Drive storage providing:
 * 1. O(1) random-access seeking at kernel FileChannel level
 * 2. Finite deadline protection for read operations
 * 3. Read-only channel safety
 * 4. Ownership and lifecycle management with non-blocking caller close
 */
public class DriveSeekableByteChannel implements SeekableByteChannel {

    private final FileChannel delegate;
    private final DriveIoExecutor ioExecutor;
    private final AtomicBoolean closed = new AtomicBoolean(false);
    private final AtomicBoolean delegateClosed = new AtomicBoolean(false);
    private final AtomicInteger activeWorkerOperations = new AtomicInteger(0);

    public DriveSeekableByteChannel(FileChannel delegate, DriveIoExecutor ioExecutor) {
        if (delegate == null) {
            throw new IllegalArgumentException("FileChannel delegate cannot be null");
        }
        if (ioExecutor == null) {
            throw new IllegalArgumentException("DriveIoExecutor cannot be null");
        }
        this.delegate = delegate;
        this.ioExecutor = ioExecutor;
    }

    private void ensureOpen() throws ClosedChannelException {
        if (closed.get()) {
            throw new ClosedChannelException();
        }
    }

    @Override
    public int read(ByteBuffer dst) throws IOException {
        ensureOpen();
        try {
            return ioExecutor.executeRead(() -> {
                ensureOpen();
                activeWorkerOperations.incrementAndGet();
                try {
                    return delegate.read(dst);
                } finally {
                    int remaining = activeWorkerOperations.decrementAndGet();
                    if (remaining == 0 && closed.get()) {
                        closeDelegateSilently();
                    }
                }
            });
        } catch (MediaUnavailableException e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException(e.getMessage(), e);
        } catch (Exception e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException("Lỗi đọc dữ liệu từ Google Drive: " + e.getMessage(), e);
        }
    }

    @Override
    public int write(ByteBuffer src) throws IOException {
        ensureOpen();
        throw new NonWritableChannelException();
    }

    @Override
    public long position() throws IOException {
        ensureOpen();
        try {
            return ioExecutor.executeMetadata(() -> {
                ensureOpen();
                activeWorkerOperations.incrementAndGet();
                try {
                    return delegate.position();
                } finally {
                    int remaining = activeWorkerOperations.decrementAndGet();
                    if (remaining == 0 && closed.get()) {
                        closeDelegateSilently();
                    }
                }
            });
        } catch (MediaUnavailableException e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException(e.getMessage(), e);
        } catch (Exception e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException("Lỗi đọc vị trí từ Google Drive: " + e.getMessage(), e);
        }
    }

    @Override
    public SeekableByteChannel position(long newPosition) throws IOException {
        ensureOpen();
        if (newPosition < 0) {
            throw new IllegalArgumentException("Vị trí đọc không hợp lệ (nhỏ hơn 0): " + newPosition);
        }
        try {
            return ioExecutor.executeMetadata(() -> {
                ensureOpen();
                activeWorkerOperations.incrementAndGet();
                try {
                    delegate.position(newPosition);
                    return this;
                } finally {
                    int remaining = activeWorkerOperations.decrementAndGet();
                    if (remaining == 0 && closed.get()) {
                        closeDelegateSilently();
                    }
                }
            });
        } catch (MediaUnavailableException e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException(e.getMessage(), e);
        } catch (Exception e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException("Lỗi thiết lập vị trí đọc trên Google Drive: " + e.getMessage(), e);
        }
    }

    @Override
    public long size() throws IOException {
        ensureOpen();
        try {
            return ioExecutor.executeMetadata(() -> {
                ensureOpen();
                activeWorkerOperations.incrementAndGet();
                try {
                    return delegate.size();
                } finally {
                    int remaining = activeWorkerOperations.decrementAndGet();
                    if (remaining == 0 && closed.get()) {
                        closeDelegateSilently();
                    }
                }
            });
        } catch (MediaUnavailableException e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException(e.getMessage(), e);
        } catch (Exception e) {
            if (closed.get()) {
                throw new ClosedChannelException();
            }
            if (e.getCause() instanceof ClosedChannelException cce) {
                throw cce;
            }
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException("Lỗi xác định kích thước tệp trên Google Drive: " + e.getMessage(), e);
        }
    }

    @Override
    public SeekableByteChannel truncate(long size) throws IOException {
        ensureOpen();
        throw new NonWritableChannelException();
    }

    @Override
    public boolean isOpen() {
        return !closed.get() && delegate.isOpen();
    }

    @Override
    public void close() throws IOException {
        if (!closed.compareAndSet(false, true)) {
            return;
        }

        // If a worker thread is actively executing an operation (read, position, size)
        // on this channel, that worker thread will close the delegate when the operation
        // completes or unblocks. The caller returns immediately (<1ms) without blocking.
        if (activeWorkerOperations.get() > 0) {
            return;
        }

        // No active worker operation in progress. Hand over delegate closure to bounded cleanup pool.
        // ABSOLUTELY NEVER fall back to synchronous delegate.close() on caller thread!
        closeDelegateAsync();
    }

    private void closeDelegateAsync() {
        if (delegateClosed.compareAndSet(false, true)) {
            try {
                ioExecutor.executeCleanupAsync(delegate, "closeChannel");
            } catch (Throwable ignored) {
                // If anything fails, NEVER call delegate.close() synchronously on caller thread!
            }
        }
    }

    private void closeDelegateSilently() {
        if (delegateClosed.compareAndSet(false, true)) {
            try {
                delegate.close();
            } catch (Throwable ignored) {
            }
        }
    }

    public boolean isClosed() {
        return closed.get();
    }

    public FileChannel getDelegate() {
        return delegate;
    }

    public DriveIoExecutor getIoExecutor() {
        return ioExecutor;
    }

    public int getActiveWorkerOperations() {
        return activeWorkerOperations.get();
    }
}
