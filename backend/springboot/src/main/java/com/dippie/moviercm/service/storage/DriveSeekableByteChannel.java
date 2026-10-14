package com.dippie.moviercm.service.storage;

import com.dippie.moviercm.exception.MediaUnavailableException;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.NonWritableChannelException;
import java.nio.channels.SeekableByteChannel;

/**
 * SeekableByteChannel wrapper for Google Drive storage providing:
 * 1. O(1) random-access seeking at kernel FileChannel level
 * 2. Finite deadline protection for read operations
 * 3. Read-only channel safety
 */
public class DriveSeekableByteChannel implements SeekableByteChannel {

    private final FileChannel delegate;
    private final DriveIoExecutor ioExecutor;

    public DriveSeekableByteChannel(FileChannel delegate, DriveIoExecutor ioExecutor) {
        this.delegate = delegate;
        this.ioExecutor = ioExecutor;
    }

    @Override
    public int read(ByteBuffer dst) throws IOException {
        try {
            return ioExecutor.executeRead(() -> delegate.read(dst));
        } catch (MediaUnavailableException e) {
            throw new IOException(e.getMessage(), e);
        } catch (Exception e) {
            if (e.getCause() instanceof IOException ioe) {
                throw ioe;
            }
            throw new IOException("Lỗi đọc dữ liệu từ Google Drive: " + e.getMessage(), e);
        }
    }

    @Override
    public int write(ByteBuffer src) {
        throw new NonWritableChannelException();
    }

    @Override
    public long position() throws IOException {
        return delegate.position();
    }

    @Override
    public SeekableByteChannel position(long newPosition) throws IOException {
        delegate.position(newPosition);
        return this;
    }

    @Override
    public long size() throws IOException {
        return delegate.size();
    }

    @Override
    public SeekableByteChannel truncate(long size) {
        throw new NonWritableChannelException();
    }

    @Override
    public boolean isOpen() {
        return delegate.isOpen();
    }

    @Override
    public void close() throws IOException {
        delegate.close();
    }
}
